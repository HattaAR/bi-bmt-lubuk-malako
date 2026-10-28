"""Operator CLI. Default is preview; --publish and --published-by are explicit."""

import argparse
import json
import sys

import pymysql

from src.database.publications import PublicationError, preview_active_candidate, publish_active_candidate


def _positive_int(value):
    try:
        result = int(value)
        if result <= 0:
            raise ValueError
        return result
    except ValueError:
        raise argparse.ArgumentTypeError("ID harus berupa bilangan bulat positif.") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Preview/publikasi kandidat data aktif; bukan ETL atau training.")
    parser.add_argument("--candidate-id", required=True, type=_positive_int)
    parser.add_argument("--published-by", type=_positive_int, help="ID pengguna aplikasi aktif dengan role admin.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preview", action="store_true", help="Preview tanpa penulisan (default).")
    mode.add_argument("--publish", action="store_true", help="Publikasikan kandidat yang lolos pemeriksaan.")
    args = parser.parse_args(argv)
    if args.publish and args.published_by is None:
        parser.error("--publish memerlukan --published-by dengan ID admin yang sudah tersedia.")
    try:
        if args.publish:
            result = publish_active_candidate(args.candidate_id, args.published_by)
        else:
            result = preview_active_candidate(args.candidate_id, published_by=args.published_by)
        print(json.dumps(result, default=str, ensure_ascii=False, indent=2))
        return 0
    except PublicationError as error:
        result = {"mode": "publish" if args.publish else "preview", "status": "failed",
                  "code": error.code, "message": str(error)}
    except pymysql.MySQLError as error:
        result = {"status": "failed", "mysql_code": error.args[0] if error.args else None,
                  "message": "Operasi MySQL gagal. Pesan driver yang dapat memuat data sensitif tidak ditampilkan."}
    except (ValueError, OSError):
        result = {"status": "failed", "message": "Operasi gagal; periksa konfigurasi, sumber, dan lock layanan."}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
