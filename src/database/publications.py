"""Preview and explicit publication for active candidates. No schema changes."""

from src.database.connection import get_connection
from src.database.active_candidates import active_write_transaction
from src.database.active_portfolio import current_active_publication
from src.database.publication_checks import (
    PublicationError, capabilities, dataset_metadata, reference_id_for_candidate,
    require_admin, validate_for_publication, warning_summaries,
)


def _inspect(cursor, dataset_id, published_by=None, *, lock=False):
    version = dataset_metadata(cursor, dataset_id, lock=lock)
    result = {"candidate": version, "reference": None, "reconciliation": None,
              "warnings": warning_summaries(cursor, [dataset_id]),
              "previous_publication": current_active_publication(cursor, lock=lock),
              "capabilities": capabilities(version["position_date"], version["position_date_status"]),
              "blockers": [], "data_valid": False, "can_publish": False}
    prepared = None
    try:
        reference_id = reference_id_for_candidate(cursor, dataset_id)
        reference = dataset_metadata(cursor, reference_id, lock=lock)
        result["reference"] = reference
        result["warnings"] = warning_summaries(cursor, [dataset_id, reference_id])
        prepared, result["reconciliation"] = validate_for_publication(cursor, version, reference, lock=lock)
        result["data_valid"] = True
    except PublicationError as error:
        result["blockers"].append({"code": error.code, "message": str(error)})
    cursor.execute("""SELECT COUNT(*) AS n FROM app_users u JOIN app_user_roles r USING(user_id)
        WHERE u.is_active=1 AND r.role_code=%s""", ("admin",))
    result["active_admin_count"] = cursor.fetchone()["n"]
    try:
        require_admin(cursor, published_by, lock=lock)
        result["published_by"] = published_by
    except PublicationError as error:
        result["blockers"].append({"code": error.code, "message": str(error)})
    result["can_publish"] = not result["blockers"]
    return result, prepared


def preview_active_candidate(dataset_id, *, published_by=None, connection_factory=get_connection):
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            connection.rollback()
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            connection.begin()
            result, _ = _inspect(cursor, dataset_id, published_by)
            connection.rollback()
    result["mode"] = "preview"
    return result


def _set_current(cursor, publication_id, previous):
    if previous is None:
        cursor.execute("INSERT INTO current_publications(dataset_kind,publication_id) VALUES(%s,%s)",
                       ("active", publication_id))
    else:
        cursor.execute("UPDATE current_publications SET publication_id=%s WHERE dataset_kind=%s AND publication_id=%s",
                       (publication_id, "active", previous["publication_id"]))
        if cursor.rowcount != 1:
            raise PublicationError("CURRENT_CHANGED", "Pointer berubah saat publikasi; transaksi dibatalkan.")


_UNSPECIFIED=object()


def publish_active_candidate(dataset_id, published_by, *, connection_factory=get_connection, lock_timeout=10,
                             expected_current_publication_id=_UNSPECIFIED):
    with active_write_transaction(connection_factory=connection_factory, lock_timeout=lock_timeout) as cursor:
        require_admin(cursor, published_by, lock=True)
        preview, prepared = _inspect(cursor, dataset_id, published_by, lock=True)
        if preview["blockers"]:
            blocker = preview["blockers"][0]
            raise PublicationError(blocker["code"], blocker["message"])
        version, reference = preview["candidate"], preview["reference"]
        previous = preview["previous_publication"]
        if (expected_current_publication_id is not _UNSPECIFIED
            and (previous['publication_id'] if previous else None)!=expected_current_publication_id
            and (previous is None or previous['dataset_version_id']!=dataset_id)):
            raise PublicationError('PREVIEW_STALE','Publikasi aktif berubah sejak preview. Periksa preview terbaru sebelum menerbitkan.')
        cursor.execute("""SELECT publication_id,dataset_version_id,reference_dataset_version_id,
            published_by,published_at,previous_publication_id FROM dataset_publications
            WHERE dataset_version_id=%s FOR UPDATE""", (dataset_id,))
        publication = cursor.fetchone()
        reused = publication is not None
        if reused:
            if (version["status"] != "published"
                    or publication["reference_dataset_version_id"] != reference["dataset_version_id"]):
                raise PublicationError("PUBLICATION_INVALID", "Riwayat publikasi tidak konsisten; tidak ditimpa.")
        else:
            if version["status"] != "ready":
                raise PublicationError("CANDIDATE_NOT_READY", "Kandidat harus ready untuk publikasi baru.")
            cursor.execute("""INSERT INTO dataset_publications(dataset_version_id,reference_dataset_version_id,
                published_by,previous_publication_id) VALUES(%s,%s,%s,%s)""",
                (dataset_id, reference["dataset_version_id"], published_by,
                 previous["publication_id"] if previous else None))
            publication_id = cursor.lastrowid
            cursor.execute("UPDATE dataset_versions SET status='published' WHERE dataset_version_id=%s AND status='ready'",
                           (dataset_id,))
            if cursor.rowcount != 1:
                raise PublicationError("STATUS_CHANGED", "Status kandidat berubah; transaksi dibatalkan.")
            _set_current(cursor, publication_id, previous)
            cursor.execute("""SELECT publication_id,dataset_version_id,reference_dataset_version_id,
                published_by,published_at,previous_publication_id FROM dataset_publications
                WHERE publication_id=%s""", (publication_id,))
            publication = cursor.fetchone()
        prepared.verify_sources()
        current_id = publication["publication_id"] if not reused else previous["publication_id"] if previous else None
        result = {**publication, "reused": reused, "is_current": current_id == publication["publication_id"],
                  "capabilities": preview["capabilities"], "mode": "publish"}
    return result
