"""CLI: prepare only by default; --load commits a candidate, never a publication."""

import argparse
from collections import Counter
import json
import sys

import pymysql
import xlrd

from src.etl.active_candidate import (
    ACTIVE_FILE, REFERENCE_FILE, MAPPING_VERSION, CandidateValidationError,
    prepare_candidate,
)


def _print(value):
    print(json.dumps(value, default=str, indent=2, ensure_ascii=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validasi/pemuatan kandidat aktif ke MySQL, tanpa publikasi.")
    parser.add_argument("--active-file", default=str(ACTIVE_FILE))
    parser.add_argument("--reference-file", default=str(REFERENCE_FILE))
    parser.add_argument("--active-sheet", default="SQLRESULT")
    parser.add_argument("--reference-sheet", default="SQLRESULT1")
    parser.add_argument("--mapping-version", default=MAPPING_VERSION)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Validasi tanpa koneksi/penulisan MySQL (default).")
    mode.add_argument("--load", action="store_true", help="Muat kandidat secara atomik; bukan publikasi.")
    args = parser.parse_args(argv)
    try:
        candidate = prepare_candidate(args.active_file, args.reference_file,
            active_sheet=args.active_sheet, reference_sheet=args.reference_sheet,
            mapping_version=args.mapping_version)
        candidate.verify_sources()
        result = {
            "dry_run": not args.load, "status": "validated",
            "ingestion_key": candidate.ingestion_key,
            "sources": {"active": candidate.active_source.identity(), "reference": candidate.reference_source.identity()},
            "position_date": None, "position_date_status": "unknown",
            "reconciliation": candidate.summary,
            "findings": dict(Counter(f.severity for f in candidate.findings)),
            # Raw values are stored in controlled DB findings, not echoed to logs.
            "warnings": [{"rule": f.rule_code, "source": f.source,
                          "row": f.source_row_number, "field": f.field_name}
                         for f in candidate.findings if f.severity == "warning"],
        }
        if args.load:
            from src.database.active_candidates import load_candidate
            stored = load_candidate(candidate)
            result.update({"dataset_version_id": stored.dataset_version_id,
                           "reference_dataset_version_id": stored.reference_dataset_version_id,
                           "status": stored.status, "reused": stored.reused,
                           "reconciliation": stored.reconciliation})
        _print(result)
        return 0
    except pymysql.MySQLError as error:
        # Driver messages can contain a full account in a duplicate-key error.
        code = error.args[0] if error.args and isinstance(error.args[0], int) else None
        _print({"status": "failed", "mysql_code": code,
                "message": "Operasi MySQL gagal; transaksi dibatalkan. Detail sensitif tidak dicetak."})
        return 1
    except CandidateValidationError as error:
        _print({"status": "failed", "message": str(error),
                "findings": [{"rule": f.rule_code, "severity": f.severity,
                              "source": f.source, "row": f.source_row_number, "field": f.field_name}
                             for f in error.findings]})
        return 1
    except (ValueError, OSError, xlrd.XLRDError):
        _print({"status": "failed", "message": "Persiapan/pemuatan kandidat gagal; periksa sumber, konfigurasi, dan skema. Tidak ada publikasi."})
        return 1


if __name__ == "__main__":
    sys.exit(main())
