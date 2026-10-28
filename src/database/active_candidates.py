"""Atomic candidate persistence for the existing MySQL/InnoDB data mart.

No publication writes, DDL, deletion, or updates to previously stored facts.
The process-wide DB advisory lock serializes this loader across connections.
"""

from dataclasses import dataclass
from contextlib import contextmanager
from decimal import Decimal
import hashlib
import json
import uuid

from src.database.connection import get_connection
from src.etl.active_candidate import CandidateValidationError, SOURCE_SYSTEM


class CandidateLoadError(ValueError):
    pass


@dataclass(frozen=True)
class LoadResult:
    dataset_version_id: int
    reference_dataset_version_id: int
    status: str
    reused: bool
    reconciliation: dict


def lock_name(cursor):
    cursor.execute("SELECT DATABASE() AS db")
    database = cursor.fetchone()["db"]
    return "bmt_active_etl:" + hashlib.sha256(database.encode("utf-8")).hexdigest()[:32]


def _insert(cursor, table, values):
    # Table and column names are internal constants, never source/user values.
    columns = ",".join(values)
    placeholders = ",".join(["%s"] * len(values))
    cursor.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(values.values()))
    return cursor.lastrowid


def _report_name(candidate, kind):
    if kind=='active' and candidate.report_metadata:return candidate.report_metadata['report_name']
    key = candidate.ingestion_key if kind == "active" else candidate.reference_key
    return f"{kind}-candidate:{key}"


def _find_version(cursor, candidate, kind):
    key=candidate.ingestion_key if kind=='active' else candidate.reference_key
    cursor.execute("""SELECT dataset_version_id, status, position_date, position_date_status,
        schema_version, mapping_version, validation_rule_version,report_name,scope_description,
        export_date,export_period_text FROM dataset_versions WHERE dataset_kind=%s AND
        (BINARY report_name=BINARY %s OR BINARY (CASE WHEN JSON_VALID(scope_description)
        THEN JSON_UNQUOTE(JSON_EXTRACT(scope_description,'$.ingestion_key')) ELSE NULL END)=BINARY %s)""",
                   (kind, f'{kind}-candidate:{key}',key))
    matches = cursor.fetchall()
    if len(matches) > 1:
        raise CandidateLoadError("Identitas kandidat berulang di database; perlu pemeriksaan manual.")
    if not matches:
        return None
    version = matches[0]
    if version["status"] not in {"ready", "published"}:
        raise CandidateLoadError("Versi existing belum ready/published; tidak ditimpa otomatis.")
    expected = (candidate.schema_version, candidate.mapping_version, candidate.validation_version)
    actual = tuple(version[k] for k in ("schema_version", "mapping_version", "validation_rule_version"))
    metadata=candidate.report_metadata if kind=='active' else None
    position=candidate.position_date if kind=='active' else None
    status=metadata['position_date_status'] if metadata else 'unknown'
    if (actual != expected or version["position_date"] != position
            or version["position_date_status"] != status):
        raise CandidateLoadError("Metadata versi existing berbeda; tidak ditimpa.")
    if metadata:
        stored=json.loads(version['scope_description'])
        if (stored.get('report_metadata')!=metadata or version['report_name']!=metadata['report_name']
            or str(version['export_date'])!=(metadata['export_date'] or 'None')
            or version['export_period_text']!=metadata['export_period_text']):
            raise CandidateLoadError('Metadata laporan existing berbeda; tidak ditimpa.')
    return version


def _source_id(cursor, source,uploaded_by=None):
    cursor.execute("SELECT source_file_id, byte_size FROM source_files WHERE file_sha256=%s ORDER BY source_file_id",
                   (source.sha256,))
    found = cursor.fetchall()
    if found:
        if any(row["byte_size"] != source.byte_size for row in found):
            raise CandidateLoadError("Metadata ukuran sumber berbeda untuk hash yang sama.")
        return found[0]["source_file_id"]
    return _insert(cursor, "source_files", {
        "original_filename": source.path.name,
        "stored_path": str(source.path), "file_sha256": source.sha256,
        "byte_size": source.byte_size, "uploaded_by": uploaded_by,
    })


def _new_version(cursor, candidate, kind):
    metadata=candidate.report_metadata if kind=='active' else None
    return _insert(cursor, "dataset_versions", {
        "dataset_kind": kind, "report_name": _report_name(candidate, kind),
        "position_date": candidate.position_date if metadata else None,
        "position_date_status": metadata['position_date_status'] if metadata else 'unknown',
        "export_date": metadata['export_date'] if metadata else None,
        "export_period_text": metadata['export_period_text'] if metadata else None,
        "scope_description": json.dumps({
            "ingestion_key": candidate.ingestion_key if kind == "active" else candidate.reference_key,
            "purpose": "Kandidat lokal; publikasi terpisah",
            "reference_key": candidate.reference_key,
            "source_system": SOURCE_SYSTEM,
            **({'report_metadata':metadata} if metadata else {}),
        }, sort_keys=True),
        "schema_version": candidate.schema_version, "mapping_version": candidate.mapping_version,
        "validation_rule_version": candidate.validation_version, "status": "validating",
    })


def _link_source(cursor, dataset_id, file_id, source, role):
    assert_dataset_mutable(cursor, dataset_id)
    _insert(cursor, "dataset_sources", {"dataset_version_id": dataset_id,
            "source_file_id": file_id, "source_role": role, "sheet_name": source.sheet})


def _save_findings(cursor, candidate, dataset_id, ids, *, reference_only=False):
    assert_dataset_mutable(cursor, dataset_id)
    for finding in candidate.findings:
        if (finding.source == "reference") != reference_only:
            continue
        _insert(cursor, "validation_findings", {
            "dataset_version_id": dataset_id, "source_file_id": ids.get(finding.source),
            "source_row_number": finding.source_row_number, "field_name": finding.field_name,
            "rule_code": finding.rule_code, "severity": finding.severity,
            "message": finding.message, "affected_function": finding.affected_function,
        })


GROUP_DIMENSIONS = (
    ("dim_marketing", "marketing_id", "marketing_code", "marketing_name", "marketing"),
    ("dim_sektor", "sector_id", "sector_code", "sector_name", "sectors"),
)


def _reference_dimensions(cursor, candidate, reference_id, *, create=False):
    if create:
        assert_dataset_mutable(cursor, reference_id)
    dimensions = {}
    for table, id_col, code_col, name_col, attribute in GROUP_DIMENSIONS:
        expected = {code: (name, "mapped") for code, name in getattr(candidate, attribute).items()}
        # One immutable unknown member per reference version. Actual unknown code
        # stays in the fact's recorded_*_code; no fabricated source category.
        expected[""] = ("Belum terpetakan", "unmapped")
        if create:
            for code, (name, status) in sorted(expected.items()):
                _insert(cursor, table, {"reference_dataset_version_id": reference_id,
                                       code_col: code, name_col: name, "mapping_status": status})
        cursor.execute(f"SELECT {id_col}, {code_col}, {name_col}, mapping_status FROM {table} WHERE reference_dataset_version_id=%s",
                       (reference_id,))
        rows = cursor.fetchall()
        actual = {row[code_col]: (row[name_col], row["mapping_status"]) for row in rows}
        if actual != expected:
            raise CandidateLoadError("Kamus existing tidak sesuai sumber tervalidasi; tidak diubah.")
        dimensions[attribute] = {row[code_col]: row[id_col] for row in rows}
    return dimensions


def _account_id(cursor, account):
    cursor.execute("SELECT account_id FROM dim_rekening WHERE source_system_code=%s AND account_number=%s",
                   (SOURCE_SYSTEM, account))
    row = cursor.fetchone()
    if row:
        return row["account_id"]
    return _insert(cursor, "dim_rekening", {"source_system_code": SOURCE_SYSTEM,
                   "account_number": account, "public_code": "acct_" + uuid.uuid4().hex})


MONTH_NAMES = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
               "Agustus", "September", "Oktober", "November", "Desember")


def _date_id(cursor, value):
    if value is None:
        return None
    key = value.year * 10000 + value.month * 100 + value.day
    cursor.execute("SELECT full_date FROM dim_tanggal WHERE date_key=%s", (key,))
    found = cursor.fetchone()
    if found:
        if found["full_date"] != value:
            raise CandidateLoadError("Dimensi tanggal existing tidak konsisten.")
        return key
    _insert(cursor, "dim_tanggal", {"date_key": key, "full_date": value,
        "day_of_month": value.day, "month_number": value.month,
        "month_name": MONTH_NAMES[value.month - 1], "quarter_number": (value.month - 1) // 3 + 1,
        "year_number": value.year, "day_of_week": value.isoweekday()})
    return key


def _fact_values(candidate, row, dataset_id, file_id, accounts, groups, categories, dates):
    return {
        "dataset_version_id": dataset_id, "account_id": accounts[row.account_number],
        "marketing_id": groups["marketing"].get(row.marketing_code, groups["marketing"][""]),
        "sector_id": groups["sectors"].get(row.sector_code, groups["sectors"][""]),
        "collectibility_id": categories[row.category],
        "realization_date_key": dates[row.realization_date], "maturity_date_key": dates[row.maturity_date],
        "original_principal": row.money["jml_pinjaman"], "outstanding_principal": row.money["saldo_nominatif"],
        "overdue_principal": row.money["tunggakan_pokok"], **row.optional,
        "recorded_marketing_code": row.marketing_code, "recorded_sector_code": row.sector_code,
        "recorded_collectibility_code": row.recorded_category,
        "contract_duration_days": row.contract_duration_days, "model_input_status": row.model_input_status,
        "source_file_id": file_id, "source_sheet": candidate.active_source.sheet,
        "source_row_number": row.source_row_number,
    }


def _verify_links(cursor, dataset_id, expected):
    cursor.execute("""SELECT s.file_sha256, ds.sheet_name, ds.source_role
        FROM dataset_sources ds JOIN source_files s USING (source_file_id)
        WHERE ds.dataset_version_id=%s""", (dataset_id,))
    actual = {(row["file_sha256"], row["sheet_name"], row["source_role"]) for row in cursor.fetchall()}
    if actual != expected:
        raise CandidateLoadError("Hubungan sumber kandidat tidak sesuai fingerprint/sheet/peran.")


def reconcile_candidate(cursor, candidate, dataset_id, reference_id):
    """Compare SQL aggregates AND every stored fact with validated Python rows."""
    groups = _reference_dimensions(cursor, candidate, reference_id)
    cursor.execute("""SELECT COUNT(*) AS rows_count, COUNT(DISTINCT f.account_id) AS unique_accounts,
        COUNT(DISTINCT a.account_number) AS unique_numbers,
        SUM(f.original_principal) AS jml_pinjaman, SUM(f.outstanding_principal) AS saldo_nominatif,
        SUM(f.overdue_principal) AS tunggakan_pokok,
        SUM(m.mapping_status='unmapped') AS unmapped_marketing,
        SUM(s.mapping_status='unmapped') AS unmapped_sector,
        SUM(m.reference_dataset_version_id<>%s OR s.reference_dataset_version_id<>%s) AS wrong_reference
        FROM fact_pembiayaan_aktif f JOIN dim_rekening a USING (account_id)
        JOIN dim_marketing m USING (marketing_id) JOIN dim_sektor s USING (sector_id)
        WHERE f.dataset_version_id=%s""", (reference_id, reference_id, dataset_id))
    stored = cursor.fetchone()
    cursor.execute("""SELECT c.collectibility_code, COUNT(*) AS n
        FROM fact_pembiayaan_aktif f JOIN dim_kolektibilitas c USING (collectibility_id)
        WHERE f.dataset_version_id=%s GROUP BY c.collectibility_code""", (dataset_id,))
    summary = {
        "rows": stored["rows_count"], "unique_accounts": stored["unique_accounts"],
        "totals": {col: stored[col] or Decimal("0.00") for col in candidate.summary["totals"]},
        "collectibility": {row["collectibility_code"]: row["n"] for row in cursor.fetchall()},
        "unmapped_marketing": int(stored["unmapped_marketing"] or 0),
        "unmapped_sector": int(stored["unmapped_sector"] or 0),
    }
    if (summary != candidate.summary or stored["unique_numbers"] != candidate.summary["unique_accounts"]
            or stored["wrong_reference"]):
        raise CandidateLoadError("Rekonsiliasi SQL/Python gagal; seluruh pemuatan dibatalkan.")
    cursor.execute("""SELECT f.*, a.account_number, a.source_system_code,
        c.collectibility_code, r.full_date AS realization_date, t.full_date AS maturity_date,
        sf.file_sha256 AS source_hash
        FROM fact_pembiayaan_aktif f JOIN dim_rekening a USING (account_id)
        JOIN dim_kolektibilitas c USING (collectibility_id)
        JOIN source_files sf USING (source_file_id)
        LEFT JOIN dim_tanggal r ON f.realization_date_key=r.date_key
        LEFT JOIN dim_tanggal t ON f.maturity_date_key=t.date_key
        WHERE f.dataset_version_id=%s ORDER BY f.source_row_number""", (dataset_id,))
    actual_rows = cursor.fetchall()
    for actual, expected in zip(actual_rows, sorted(candidate.rows, key=lambda r: r.source_row_number)):
        checks = {
            "account_number": expected.account_number, "source_system_code": SOURCE_SYSTEM,
            "source_row_number": expected.source_row_number, "source_sheet": candidate.active_source.sheet,
            "source_hash": candidate.active_source.sha256, "collectibility_code": expected.category,
            "recorded_marketing_code": expected.marketing_code, "recorded_sector_code": expected.sector_code,
            "recorded_collectibility_code": expected.recorded_category,
            "marketing_id": groups["marketing"].get(expected.marketing_code, groups["marketing"][""]),
            "sector_id": groups["sectors"].get(expected.sector_code, groups["sectors"][""]),
            "original_principal": expected.money["jml_pinjaman"],
            "outstanding_principal": expected.money["saldo_nominatif"],
            "overdue_principal": expected.money["tunggakan_pokok"],
            "realization_date": expected.realization_date, "maturity_date": expected.maturity_date,
            "contract_duration_days": expected.contract_duration_days,
            "model_input_status": expected.model_input_status, **expected.optional,
        }
        if any(actual[column] != value for column, value in checks.items()):
            raise CandidateLoadError("Rekonsiliasi record/lineage gagal; seluruh pemuatan dibatalkan.")
    active_identity = candidate.active_source.identity()
    ref_identity = candidate.reference_source.identity()
    _verify_links(cursor, dataset_id, {
        (active_identity["sha256"], active_identity["sheet"], "active_primary"),
        (ref_identity["sha256"], ref_identity["sheet"], "reference_dictionary"),
    })
    _verify_links(cursor, reference_id, {(ref_identity["sha256"], ref_identity["sheet"], "reference_dictionary")})
    return summary


def store_candidate(cursor, candidate,*,uploaded_by=None):
    """Store/reuse inside caller's transaction, under the loader advisory lock.

    Does not commit. Exposed separately for rollback-only integration tests.
    """
    if any(f.severity == "blocking" for f in candidate.findings):
        raise CandidateValidationError("Temuan blocking tidak boleh dimuat.")
    existing = _find_version(cursor, candidate, "active")
    reference = _find_version(cursor, candidate, "reference")
    if existing:
        if reference is None:
            raise CandidateLoadError("Versi kamus kandidat existing tidak ditemukan.")
        dataset_id, reference_id = existing["dataset_version_id"], reference["dataset_version_id"]
        summary = reconcile_candidate(cursor, candidate, dataset_id, reference_id)
        return LoadResult(dataset_id, reference_id, existing["status"], True, summary)

    ids = {"active": _source_id(cursor, candidate.active_source,uploaded_by),
           "reference": _source_id(cursor, candidate.reference_source,uploaded_by)}
    if reference is None:
        reference_id = _new_version(cursor, candidate, "reference")
        _link_source(cursor, reference_id, ids["reference"], candidate.reference_source, "reference_dictionary")
        groups = _reference_dimensions(cursor, candidate, reference_id, create=True)
        _save_findings(cursor, candidate, reference_id, ids, reference_only=True)
        cursor.execute("UPDATE dataset_versions SET status='ready' WHERE dataset_version_id=%s AND status='validating'",
                       (reference_id,))
    else:
        reference_id = reference["dataset_version_id"]
        groups = _reference_dimensions(cursor, candidate, reference_id)

    dataset_id = _new_version(cursor, candidate, "active")
    _link_source(cursor, dataset_id, ids["active"], candidate.active_source, "active_primary")
    _link_source(cursor, dataset_id, ids["reference"], candidate.reference_source, "reference_dictionary")
    cursor.execute("SELECT collectibility_id, collectibility_code FROM dim_kolektibilitas")
    categories = {row["collectibility_code"]: row["collectibility_id"] for row in cursor.fetchall()}
    if not {"L", "KL", "D", "M", "UNKNOWN"}.issubset(categories):
        raise CandidateLoadError("Dimensi kolektibilitas belum lengkap.")
    accounts = {account: _account_id(cursor, account) for account in sorted(row.account_number for row in candidate.rows)}
    dates = {None: None}
    used_dates = {value for row in candidate.rows for value in (row.realization_date, row.maturity_date) if value}
    for value in sorted(used_dates):
        dates[value] = _date_id(cursor, value)
    for row in candidate.rows:
        _insert(cursor, "fact_pembiayaan_aktif", _fact_values(
            candidate, row, dataset_id, ids["active"], accounts, groups, categories, dates))
    _save_findings(cursor, candidate, dataset_id, ids)
    summary = reconcile_candidate(cursor, candidate, dataset_id, reference_id)
    _insert(cursor, "validation_findings", {
        "dataset_version_id": dataset_id, "source_file_id": ids["active"],
        "rule_code": "RECONCILIATION_PASSED", "severity": "information",
        "message": json.dumps(summary, default=str, sort_keys=True), "affected_function": "etl_active",
    })
    cursor.execute("UPDATE dataset_versions SET status='ready' WHERE dataset_version_id=%s AND status='validating'",
                   (dataset_id,))
    if cursor.rowcount != 1:
        raise CandidateLoadError("Kandidat tidak dapat ditandai ready.")
    return LoadResult(dataset_id, reference_id, "ready", False, summary)


def _check_transaction_support(cursor):
    required = {"source_files", "dataset_versions", "dataset_sources", "dim_marketing", "dim_sektor",
                "dim_rekening", "dim_tanggal", "dim_kolektibilitas", "fact_pembiayaan_aktif", "validation_findings",
                "dataset_publications", "current_publications", "app_users", "app_user_roles"}
    cursor.execute("""SELECT TABLE_NAME AS name, ENGINE AS engine FROM information_schema.TABLES
        WHERE TABLE_SCHEMA=DATABASE()""")
    engines = {row["name"]: row["engine"] for row in cursor.fetchall()}
    if any(engines.get(table) != "InnoDB" for table in required):
        raise CandidateLoadError("Tabel wajib harus tersedia dan menggunakan InnoDB.")
    cursor.execute("SELECT @@SESSION.sql_mode AS mode")
    if not {"STRICT_TRANS_TABLES", "STRICT_ALL_TABLES"}.intersection(cursor.fetchone()["mode"].split(",")):
        raise CandidateLoadError("MySQL strict mode diperlukan untuk mencegah pemotongan data.")


def assert_dataset_mutable(cursor, dataset_id):
    """Write guard, including ready dictionaries referenced by any publication.

    Call under active_write_transaction before editing version-owned content.
    Raw SQL by database administrators is outside this application guard.
    """
    cursor.execute("SELECT status FROM dataset_versions WHERE dataset_version_id=%s FOR UPDATE", (dataset_id,))
    row = cursor.fetchone()
    if row is None:
        raise CandidateLoadError("Versi yang akan ditulis tidak ditemukan.")
    cursor.execute("""SELECT publication_id FROM dataset_publications
        WHERE dataset_version_id=%s OR reference_dataset_version_id=%s LIMIT 1""", (dataset_id, dataset_id))
    if row["status"] == "published" or cursor.fetchone() is not None:
        raise CandidateLoadError("Versi terpublikasi/dirujuk publikasi bersifat immutable; buat versi baru.")


@contextmanager
def active_write_transaction(*, connection_factory=get_connection, lock_timeout=10):
    """Shared ETL/publication lock and transaction. Factory must create a connection."""
    connection = connection_factory()
    acquired = False
    name = None
    try:
        with connection.cursor() as cursor:
            _check_transaction_support(cursor)
            name = lock_name(cursor)
            cursor.execute("SELECT GET_LOCK(%s,%s) AS acquired", (name, lock_timeout))
            acquired = cursor.fetchone()["acquired"] == 1
            if not acquired:
                raise CandidateLoadError("Loader lain sedang berjalan; coba ulang setelah selesai.")
            connection.rollback()
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            connection.begin()
            yield cursor
            connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        try:
            if acquired:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", (name,))
        finally:
            connection.close()


def load_candidate(candidate, *, connection_factory=get_connection, lock_timeout=10,admin_user_id=None):
    candidate.verify_sources()
    with active_write_transaction(connection_factory=connection_factory, lock_timeout=lock_timeout) as cursor:
        if admin_user_id is not None:
            from src.database.publication_checks import require_admin
            require_admin(cursor,admin_user_id,lock=True)
        result = store_candidate(cursor, candidate,uploaded_by=admin_user_id)
        candidate.verify_sources()
    return result
