"""Dashboard reads use exactly the active publication pointer in one snapshot."""

from src.database.connection import get_connection
from src.database.publication_checks import PublicationError, capabilities


def current_active_publication(cursor, *, lock=False):
    cursor.execute("""SELECT cp.publication_id,p.dataset_version_id,p.reference_dataset_version_id,
        p.published_by,p.published_at,p.previous_publication_id,
        d.dataset_kind,d.status,d.position_date,d.position_date_status,
        r.dataset_kind AS reference_kind,r.status AS reference_status
        FROM current_publications cp LEFT JOIN dataset_publications p USING(publication_id)
        LEFT JOIN dataset_versions d ON p.dataset_version_id=d.dataset_version_id
        LEFT JOIN dataset_versions r ON p.reference_dataset_version_id=r.dataset_version_id
        WHERE cp.dataset_kind=%s""" + (" FOR UPDATE" if lock else ""), ("active",))
    current = cursor.fetchone()
    if current is None:
        return None
    if (current["dataset_kind"] != "active" or current["status"] != "published"
            or current["reference_kind"] != "reference" or current["reference_status"] not in {"ready", "published"}):
        raise PublicationError("CURRENT_INVALID", "Pointer publikasi aktif tidak konsisten; tidak memakai fallback kandidat.")
    return current


def read_active_portfolio(*, connection_factory=get_connection):
    """Trusted internal service; the future UI must apply its role guards.

    No full account numbers returned. IDs/public_code bind detail navigation to
    this dataset version. No publication means no dashboard data.
    """
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            connection.rollback()
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            connection.begin()
            publication = current_active_publication(cursor)
            rows = []
            if publication:
                cursor.execute("""SELECT f.*,a.public_code,m.marketing_name,s.sector_name,c.collectibility_code
                    FROM fact_pembiayaan_aktif f JOIN dim_rekening a USING(account_id)
                    JOIN dim_marketing m USING(marketing_id) JOIN dim_sektor s USING(sector_id)
                    JOIN dim_kolektibilitas c USING(collectibility_id)
                    WHERE f.dataset_version_id=%s AND m.reference_dataset_version_id=%s
                    AND s.reference_dataset_version_id=%s ORDER BY f.active_fact_id""",
                    (publication["dataset_version_id"], publication["reference_dataset_version_id"],
                     publication["reference_dataset_version_id"]))
                rows = list(cursor.fetchall())
                cursor.execute("SELECT COUNT(*) AS n FROM fact_pembiayaan_aktif WHERE dataset_version_id=%s",
                               (publication["dataset_version_id"],))
                if len(rows) != cursor.fetchone()["n"]:
                    raise PublicationError("ACTIVE_ROWS_INVALID", "Relasi fakta/kamus publikasi tidak konsisten; hasil parsial ditolak.")
            connection.rollback()
    return {"publication": publication, "rows": rows,
            "capabilities": capabilities(publication["position_date"], publication["position_date_status"])
            if publication else {"static_bi": False, "position_based_features": False, "position_trends": False}}
