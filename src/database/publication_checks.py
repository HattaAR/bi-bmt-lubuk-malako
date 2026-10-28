"""Read-only publication checks using the ETL validator and original source hashes."""

from collections import Counter
import json
from pathlib import Path

import xlrd

from src.database.active_candidates import _find_version, reconcile_candidate
from src.etl.active_candidate import (
    SCHEMA_VERSION, VALIDATION_VERSION, prepare_candidate,
)


class PublicationError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def capabilities(position_date, position_status):
    confirmed = position_date is not None and position_status == "confirmed"
    return {"static_bi": True, "position_based_features": confirmed,
            "position_trends": False}  # Two comparable confirmed positions still required.


def dataset_metadata(cursor, dataset_id, *, lock=False):
    cursor.execute("""SELECT dataset_version_id,dataset_kind,report_name,status,
        position_date,position_date_status,schema_version,mapping_version,validation_rule_version,
        export_date,export_period_text,scope_description
        FROM dataset_versions WHERE dataset_version_id=%s""" + (" FOR UPDATE" if lock else ""), (dataset_id,))
    row = cursor.fetchone()
    if not row:
        raise PublicationError("DATASET_NOT_FOUND", "Versi dataset tidak ditemukan.")
    return row


def require_admin(cursor, user_id, *, lock=False):
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise PublicationError("ADMIN_REQUIRED", "Pilih ID pengguna aktif dengan role admin.")
    suffix = " FOR UPDATE" if lock else ""
    cursor.execute("SELECT is_active FROM app_users WHERE user_id=%s" + suffix, (user_id,))
    user = cursor.fetchone()
    cursor.execute("SELECT role_code FROM app_user_roles WHERE user_id=%s AND role_code=%s" + suffix,
                   (user_id, "admin"))
    role = cursor.fetchone()
    if not user or not user["is_active"] or not role:
        raise PublicationError("ADMIN_REQUIRED", "published_by harus menunjuk pengguna aktif dengan role admin.")


def reference_id_for_candidate(cursor, dataset_id):
    cursor.execute("""SELECT DISTINCT m.reference_dataset_version_id AS marketing_reference,
        s.reference_dataset_version_id AS sector_reference
        FROM fact_pembiayaan_aktif f JOIN dim_marketing m USING(marketing_id)
        JOIN dim_sektor s USING(sector_id) WHERE f.dataset_version_id=%s""", (dataset_id,))
    references = {value for row in cursor.fetchall() for value in row.values()}
    if len(references) != 1:
        raise PublicationError("REFERENCE_INVALID", "Fakta harus menunjuk tepat satu versi kamus yang konsisten.")
    return references.pop()


def warning_summaries(cursor, dataset_ids):
    placeholders = ",".join(["%s"] * len(dataset_ids))
    cursor.execute(f"""SELECT dataset_version_id,rule_code,source_row_number,field_name,affected_function
        FROM validation_findings WHERE dataset_version_id IN ({placeholders})
        AND severity='warning' ORDER BY dataset_version_id,finding_id""", tuple(dataset_ids))
    # Do not return arbitrary message/raw values in the CLI or preview logs.
    return list(cursor.fetchall())


def _verify_findings(cursor, candidate, dataset_id, reference_id, sources, summary):
    cursor.execute("""SELECT dataset_version_id,source_file_id,source_row_number,field_name,
        rule_code,severity,message,affected_function FROM validation_findings
        WHERE dataset_version_id IN (%s,%s)""", (dataset_id, reference_id))
    found = cursor.fetchall()
    if any(f["severity"] == "blocking" for f in found):
        raise PublicationError("BLOCKING_FINDING", "Temuan blocking aktif/kamus belum diselesaikan.")
    keys = ("dataset_version_id", "source_file_id", "source_row_number", "field_name",
            "rule_code", "severity", "message", "affected_function")
    actual = Counter(tuple(f[key] for key in keys) for f in found if f["severity"] == "warning")
    expected = Counter((reference_id if f.source == "reference" else dataset_id,
                        sources.get(f.source), f.source_row_number, f.field_name,
                        f.rule_code, f.severity, f.message, f.affected_function)
                       for f in candidate.findings if f.severity == "warning")
    if expected - actual:
        raise PublicationError("FINDINGS_CHANGED", "Warning wajib/lineage tidak cocok dengan validasi ulang.")
    controls = [f for f in found if f["dataset_version_id"] == dataset_id
                and f["rule_code"] == "RECONCILIATION_PASSED" and f["severity"] == "information"]
    if len(controls) != 1:
        raise PublicationError("CONTROL_MISSING", "Diperlukan tepat satu hasil rekonsiliasi tersimpan.")
    try:
        matches = json.loads(controls[0]["message"]) == json.loads(json.dumps(summary, default=str))
    except (ValueError, TypeError):
        matches = False
    if not matches:
        raise PublicationError("CONTROL_CHANGED", "Kontrol tersimpan berbeda dari rekonsiliasi terkini.")


def validate_for_publication(cursor, version, reference, *, lock=False):
    dataset_id = version["dataset_version_id"]
    reference_id = reference["dataset_version_id"]
    if version["dataset_kind"] != "active" or version["status"] not in {"ready", "published"}:
        raise PublicationError("CANDIDATE_NOT_READY", "Hanya kandidat aktif ready yang dapat dipublikasikan.")
    if reference["dataset_kind"] != "reference" or reference["status"] not in {"ready", "published"}:
        raise PublicationError("REFERENCE_NOT_READY", "Versi kamus belum siap.")
    if (version["schema_version"] != SCHEMA_VERSION
            or version["validation_rule_version"] != VALIDATION_VERSION):
        raise PublicationError("RULE_VERSION_UNSUPPORTED", "Versi aturan kandidat tidak didukung validator ini.")
    cursor.execute("""SELECT ds.source_role,ds.sheet_name,s.source_file_id,s.stored_path,
        s.file_sha256,s.byte_size FROM dataset_sources ds JOIN source_files s USING(source_file_id)
        WHERE ds.dataset_version_id=%s""", (dataset_id,))
    source_rows = cursor.fetchall()
    sources = {row["source_role"]: row for row in source_rows}
    if len(source_rows) != 2 or set(sources) != {"active_primary", "reference_dictionary"}:
        raise PublicationError("SOURCES_INVALID", "Sumber utama/referensi kandidat tidak lengkap atau ambigu.")
    active, ref = sources["active_primary"], sources["reference_dictionary"]
    try:
        prepared = prepare_candidate(Path(active["stored_path"]), Path(ref["stored_path"]),
            active_sheet=active["sheet_name"], reference_sheet=ref["sheet_name"],
            mapping_version=version["mapping_version"])
        scope=json.loads(version['scope_description']) if version.get('scope_description') else {}
        if scope.get('report_metadata'):
            from src.services.admin_upload import attach_metadata
            prepared=attach_metadata(prepared,scope['report_metadata'])
        for source, stored in ((prepared.active_source, active), (prepared.reference_source, ref)):
            if (source.sha256, source.byte_size) != (stored["file_sha256"], stored["byte_size"]):
                raise PublicationError("SOURCE_CHANGED", "Hash/ukuran berkas sumber berubah; muat kandidat baru.")
        active_match = _find_version(cursor, prepared, "active")
        reference_match = _find_version(cursor, prepared, "reference")
        if (not active_match or active_match["dataset_version_id"] != dataset_id
                or not reference_match or reference_match["dataset_version_id"] != reference_id):
            raise PublicationError("IDENTITY_CHANGED", "Identitas sumber, sheet, aturan, atau versi kamus tidak cocok.")
        summary = reconcile_candidate(cursor, prepared, dataset_id, reference_id)
        _verify_findings(cursor, prepared, dataset_id, reference_id,
                         {"active": active["source_file_id"], "reference": ref["source_file_id"]}, summary)
        prepared.verify_sources()
    except PublicationError:
        raise
    except (OSError, ValueError, xlrd.XLRDError):
        raise PublicationError("REVALIDATION_FAILED", "Validasi ulang sumber/fakta/kamus gagal; tidak dipublikasikan.") from None
    return prepared, summary
