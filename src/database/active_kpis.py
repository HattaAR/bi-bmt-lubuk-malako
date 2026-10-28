"""Shared active-financing KPI service. One published version and one scope per request."""

from decimal import Decimal, localcontext

from src.database.active_portfolio import current_active_publication
from src.database.connection import get_connection
from src.database.active_review import read_review


KNOWN_CODES = ("L", "KL", "D", "M")
CATEGORY_ORDER = (*KNOWN_CODES, "UNKNOWN")
MONEY_FIELDS = ("original_principal", "outstanding_principal", "overdue_principal")
KPI_FIELDS = ("active_contracts", *MONEY_FIELDS, "contracts_with_arrears", "npf_outstanding", "npf_percent")
ZERO = Decimal("0.00")


class KPIDataError(ValueError):
    """Published data has inconsistent references; do not show partial totals."""


def _validate_id(value):
    if value is not None and (isinstance(value, bool) or not isinstance(value, int)
                              or value <= 0 or value > 18446744073709551615):
        raise ValueError("Filter harus ID dimensi berupa bilangan bulat positif atau None.")


def _percentage(numerator, denominator):
    if denominator == 0:
        return None
    with localcontext() as context:
        context.prec = 50
        return Decimal(numerator) / Decimal(denominator) * Decimal(100)


def _aggregate_groups(cursor, publication, filters, *, dimension=None):
    dimensions = {'sector':('f.sector_id','s.sector_name','s.mapping_status'),
                  'marketing':('f.marketing_id','m.marketing_name','m.mapping_status')}
    if dimension is not None and dimension not in dimensions:
        raise ValueError('Dimensi tidak dikenali.')
    columns = dimensions.get(dimension)
    extra = (f'{columns[0]} AS group_id,{columns[1]} AS group_label,{columns[2]} AS dimension_status,'
             if columns else '')
    where = ["f.dataset_version_id=%s"]
    params = [*KNOWN_CODES, "UNKNOWN", publication["reference_dataset_version_id"],
              publication["reference_dataset_version_id"], publication["dataset_version_id"]]
    for column in ("marketing_id", "sector_id"):
        if filters[column] is not None:
            # Column names are a fixed allowlist; every value is bound.
            where.append(f"f.{column}=%s")
            params.append(filters[column])
    cursor.execute("SELECT " + extra + """
        CASE WHEN c.collectibility_code IN (%s,%s,%s,%s)
             THEN c.collectibility_code ELSE %s END AS category,
        COUNT(*) AS contracts,
        SUM(f.original_principal) AS original_principal,
        SUM(f.outstanding_principal) AS outstanding_principal,
        SUM(f.overdue_principal) AS overdue_principal,
        SUM(f.overdue_principal > 0) AS contracts_with_arrears,
        SUM(CASE WHEN m.reference_dataset_version_id IS NULL
                       OR s.reference_dataset_version_id IS NULL
                       OR m.reference_dataset_version_id<>%s
                       OR s.reference_dataset_version_id<>%s THEN 1 ELSE 0 END) AS invalid_reference
        FROM fact_pembiayaan_aktif f
        LEFT JOIN dim_marketing m ON f.marketing_id=m.marketing_id
        LEFT JOIN dim_sektor s ON f.sector_id=s.sector_id
        LEFT JOIN dim_kolektibilitas c ON f.collectibility_id=c.collectibility_id
        WHERE """ + " AND ".join(where) + " GROUP BY category" +
                   (','+','.join(columns) if columns else ''), tuple(params))
    groups = list(cursor.fetchall())
    if any(row["invalid_reference"] for row in groups):
        raise KPIDataError("Kamus fakta tidak sesuai publikasi; KPI tidak dapat ditampilkan.")
    return groups


def _summarize(publication, filters, groups):
    result = {
        "publication": publication, "filters": filters,
        "npf_contracts": None,
        "status": "no_publication" if publication is None else "available",
        "kpis": dict.fromkeys(KPI_FIELDS), "composition": [],
        "unknown_collectibility_contracts": None,
        "npf_reason": "no_publication" if publication is None else None,
        "availability": {"nominal_kpis": False, "npf": False, "composition": False,
                         "contract_shares": False, "outstanding_shares": False},
        "capabilities": {"static_bi": publication is not None,
                         "position_based_features": False, "position_trends": False},
    }
    if publication is None:
        return result
    count = sum(int(row["contracts"]) for row in groups)
    totals = {field: sum((row[field] for row in groups), ZERO) for field in MONEY_FIELDS}
    npf_outstanding = sum((row["outstanding_principal"] for row in groups
                           if row["category"] in {"KL", "D", "M"}), ZERO)
    unknown = sum(int(row["contracts"]) for row in groups if row["category"] == "UNKNOWN")
    outstanding = totals["outstanding_principal"]
    result["kpis"] = {"active_contracts": count, **totals,
                      "contracts_with_arrears": sum(int(row["contracts_with_arrears"]) for row in groups),
                      "npf_outstanding": npf_outstanding, "npf_percent": None}
    result["unknown_collectibility_contracts"] = unknown
    result["npf_contracts"] = sum(int(row["contracts"]) for row in groups if row["category"] in {"KL", "D", "M"})
    if count == 0:
        result["status"] = "empty_selection"
        result["npf_reason"] = "empty_selection"
    else:
        result["status"] = "partial" if unknown else "available"
        result["availability"].update(nominal_kpis=True, composition=True, contract_shares=True,
                                      outstanding_shares=outstanding != 0)
        if outstanding == 0:
            result["npf_reason"] = "zero_outstanding"
        elif unknown:
            result["npf_reason"] = "unknown_collectibility"
        else:
            result["availability"]["npf"] = True
            result["kpis"]["npf_percent"] = _percentage(npf_outstanding, outstanding)
    by_category = {row["category"]: row for row in groups}
    for code in CATEGORY_ORDER:
        row = by_category.get(code)
        contracts = int(row["contracts"]) if row else 0
        amount = row["outstanding_principal"] if row else ZERO
        result["composition"].append({
            "code": code, "contracts": contracts, "outstanding_principal": amount,
            "overdue_principal": row["overdue_principal"] if row else ZERO,
            "contract_share_percent": _percentage(contracts, count),
            "outstanding_share_percent": _percentage(amount, outstanding),
        })
    return result


def _dashboard_context(cursor, publication):
    context = {"marketing": [], "sectors": [], "sources": [], "findings": []}
    if not publication:
        return context
    reference = publication["reference_dataset_version_id"]
    for table, key, name, target in (
        ("dim_marketing", "marketing_id", "marketing_name", "marketing"),
        ("dim_sektor", "sector_id", "sector_name", "sectors"),
    ):
        cursor.execute(f"SELECT {key} AS id,{name} AS label FROM {table} "
                       f"WHERE reference_dataset_version_id=%s ORDER BY {name},{key}", (reference,))
        context[target] = list(cursor.fetchall())
    cursor.execute("""SELECT sf.original_filename,ds.sheet_name,ds.source_role
        FROM dataset_sources ds JOIN source_files sf USING(source_file_id)
        WHERE ds.dataset_version_id=%s ORDER BY ds.source_role,sf.original_filename""",
                   (publication["dataset_version_id"],))
    context["sources"] = list(cursor.fetchall())
    # Aggregate rule codes only: raw values/messages may contain private identifiers.
    cursor.execute("""SELECT severity,rule_code,COUNT(*) AS findings_count
        FROM validation_findings WHERE dataset_version_id IN (%s,%s)
        GROUP BY severity,rule_code ORDER BY severity,rule_code""",
                   (publication["dataset_version_id"], reference))
    context["findings"] = list(cursor.fetchall())
    return context


def get_active_kpis(*, marketing_id=None, sector_id=None, include_context=False, connection_factory=get_connection):
    """Return Decimal amounts/percentages, status, filters, and pinned publication.

    Trusted internal service; dashboard pages must add their role guards.
    No original account numbers, row details, model scores, or date indicators.
    The connection factory must create a new connection owned by this request.
    """
    _validate_id(marketing_id)
    _validate_id(sector_id)
    filters = {"marketing_id": marketing_id, "sector_id": sector_id}
    connection = connection_factory()
    try:
        with connection.cursor() as cursor:
            connection.rollback()
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cursor.execute("START TRANSACTION READ ONLY")
            publication = current_active_publication(cursor)
            groups = _aggregate_groups(cursor, publication, filters) if publication else []
            result = _summarize(publication, filters, groups)
            if include_context:
                result["context"] = _dashboard_context(cursor, publication)
                result["context"]["review"] = read_review(cursor, publication, filters)
            return result
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
