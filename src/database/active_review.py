"""Read-only review list inside the caller's pinned publication transaction."""


def financing_code(dataset_id, fact_id):
    return f'PB-{dataset_id:06d}-{fact_id:06d}'


def review_reason(overdue, code):
    reasons = []
    if overdue > 0:reasons.append('Tunggakan pokok tercatat')
    if code in {'KL','D','M'}:reasons.append('Kolektibilitas '+code)
    return '; '.join(reasons) or 'Tidak memenuhi kriteria Perlu Ditinjau; cakupan semua pembiayaan'


def read_review(cursor, publication, filters, *, limit=4):
    if publication is None:
        return {"rows": [], "total": 0, "limit": limit}
    where = ["f.dataset_version_id=%s",
             "(f.overdue_principal>0 OR c.collectibility_code IN ('KL','D','M'))"]
    params = [publication["dataset_version_id"]]
    for column in ("marketing_id", "sector_id"):
        if filters[column] is not None:
            where.append(f"f.{column}=%s")
            params.append(filters[column])
    joins = """FROM fact_pembiayaan_aktif f
        LEFT JOIN dim_kolektibilitas c USING(collectibility_id)
        LEFT JOIN dim_marketing m USING(marketing_id)
        LEFT JOIN dim_tanggal t ON f.maturity_date_key=t.date_key WHERE """ + " AND ".join(where)
    cursor.execute("SELECT COUNT(*) AS total " + joins, tuple(params))
    total = cursor.fetchone()["total"]
    cursor.execute("""SELECT f.active_fact_id,m.marketing_name,c.collectibility_code,
        f.outstanding_principal,f.overdue_principal,t.full_date AS maturity_date """ + joins +
        " ORDER BY f.overdue_principal DESC,f.outstanding_principal DESC,f.active_fact_id ASC LIMIT %s",
        (*params, limit))
    rows = list(cursor.fetchall())
    for row in rows:
        row["financing_code"] = financing_code(publication['dataset_version_id'],row.pop('active_fact_id'))
        row['review_reason'] = review_reason(row['overdue_principal'],row['collectibility_code'])
    return {"rows": rows, "total": total, "limit": limit}
