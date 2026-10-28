"""Explicit historical operator CLI. Default dry-run never opens MySQL."""
import argparse,json
from collections import Counter
import pymysql
from src.etl.historical import prepare_historical,DEFAULT_FILE


def main(argv=None):
    p=argparse.ArgumentParser(description='Historis SQLRESULT: validasi, kandidat, publikasi terpisah.')
    p.add_argument('--file',default=str(DEFAULT_FILE));p.add_argument('--sheet',default='SQLRESULT')
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--dry-run',action='store_true');mode.add_argument('--apply-schema',action='store_true')
    mode.add_argument('--load',action='store_true');mode.add_argument('--preview',type=int);mode.add_argument('--publish',type=int)
    p.add_argument('--published-by',type=int)
    args=p.parse_args(argv)
    try:
        if args.apply_schema:
            from src.database.historical_schema import apply_historical_schema
            from src.database.connection import get_connection
            with get_connection() as c:apply_historical_schema(c)
            result={'mode':'schema','status':'applied'}
        elif args.preview is not None or args.publish is not None:
            from src.database.historical import publish_historical
            result=publish_historical(args.preview if args.preview is not None else args.publish,args.published_by,publish=args.publish is not None)
        else:
            candidate=prepare_historical(args.file,sheet=args.sheet)
            result={'mode':'load' if args.load else 'dry_run','source_sha256':candidate.source.sha256,'summary':candidate.summary,
                'date_findings':dict(Counter(issue for r in candidate.rows for issue in r['date_issues']))}
            if args.load:
                from src.database.historical import load_historical
                result.update(load_historical(candidate))
        print(json.dumps(result,default=str,ensure_ascii=False,indent=2));return 0
    except Exception as error:
        # Source values, credentials, and driver messages must not enter logs.
        print(json.dumps({'status':'failed','message':'Operasi historis gagal; periksa sumber, kandidat, admin, dan skema. Tidak ada detail sensitif dicetak.',
                          'mysql_code':error.args[0] if isinstance(error,pymysql.MySQLError) and isinstance(error.args[0],int) else None}));return 1


if __name__=='__main__':raise SystemExit(main())
