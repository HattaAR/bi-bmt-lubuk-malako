"""Read-only CLI for active KPIs. Does not return account numbers or row details."""

import argparse
import json
import sys

import pymysql

from src.database.active_kpis import KPIDataError, get_active_kpis
from src.database.publication_checks import PublicationError


def main(argv=None):
    parser = argparse.ArgumentParser(description="Periksa KPI publikasi aktif; hanya membaca database.")
    parser.add_argument("--marketing-id",type=int,help="ID dimensi marketing; default seluruh cakupan.")
    parser.add_argument("--sector-id",type=int,help="ID dimensi sektor; default seluruh cakupan.")
    args = parser.parse_args(argv)
    try:
        result = get_active_kpis(marketing_id=args.marketing_id,sector_id=args.sector_id)
        print(json.dumps({"mode":"read_only",**result},default=str,ensure_ascii=False,indent=2))
        return 0
    except PublicationError as error:
        result = {"status":"failed","code":error.code,"message":str(error)}
    except KPIDataError:
        result = {"status":"failed","code":"INVALID_DATA_REFERENCE",
                  "message":"Referensi data tidak konsisten; KPI ditolak."}
    except pymysql.MySQLError as error:
        code = error.args[0] if error.args and isinstance(error.args[0],int) else None
        result = {"status":"failed","mysql_code":code,
                  "message":"Pembacaan MySQL gagal; pesan driver sensitif tidak ditampilkan."}
    except (ValueError,OSError):
        result = {"status":"failed","message":"Periksa ID filter atau konfigurasi database."}
    print(json.dumps({"mode":"read_only",**result},ensure_ascii=False,indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
