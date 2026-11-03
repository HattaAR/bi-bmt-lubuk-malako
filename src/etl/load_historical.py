"""Explicit historical operator CLI. Default dry-run never opens MySQL."""
import argparse,json
from collections import Counter
import pymysql
from src.etl.historical import prepare_historical,DEFAULT_FILE


def historical_status(connection_factory):
    """Read-only operator discovery, including real admin IDs; no account data."""
    connection=connection_factory()
    try:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute('START TRANSACTION READ ONLY')
            cursor.execute('SELECT DATABASE() AS database_name,VERSION() AS mysql_version');result=cursor.fetchone()
            cursor.execute("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='fact_pembiayaan_historis'")
            result['fact_table_exists']=bool(cursor.fetchone())
            cursor.execute("SELECT TRIGGER_NAME FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE() AND EVENT_OBJECT_TABLE='fact_pembiayaan_historis' ORDER BY TRIGGER_NAME")
            result['protection_triggers']=[r['TRIGGER_NAME'] for r in cursor.fetchall()]
            cursor.execute("SELECT u.user_id FROM app_users u JOIN app_user_roles r USING(user_id) WHERE u.is_active=1 AND r.role_code='admin' ORDER BY u.user_id")
            result['active_admin_ids']=[r['user_id'] for r in cursor.fetchall()]
            cursor.execute('''SELECT cp.dataset_kind,cp.publication_id,p.dataset_version_id
                FROM current_publications cp JOIN dataset_publications p USING(publication_id) ORDER BY cp.dataset_kind''')
            result['current_publications']=cursor.fetchall()
            result['mode']='status';return result
    finally:
        try:connection.rollback()
        finally:connection.close()


def main(argv=None,*,connection_factory=None):
    p=argparse.ArgumentParser(description='Historis SQLRESULT: validasi, kandidat, publikasi terpisah.')
    p.add_argument('--file',default=str(DEFAULT_FILE));p.add_argument('--sheet',default='SQLRESULT')
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--dry-run',action='store_true');mode.add_argument('--apply-schema',action='store_true')
    mode.add_argument('--load',action='store_true');mode.add_argument('--preview',type=int);mode.add_argument('--publish',type=int)
    mode.add_argument('--status',action='store_true')
    p.add_argument('--published-by','--admin-id',dest='admin_id',type=int,help='ID admin aktif; wajib untuk schema/load/preview/publish.')
    args=p.parse_args(argv)
    try:
        if connection_factory is None:
            from src.database.connection import get_connection
            connection_factory=get_connection
        if args.status:result=historical_status(connection_factory)
        elif args.apply_schema:
            from src.database.historical_schema import apply_historical_schema
            from src.database.publication_checks import require_admin
            with connection_factory() as c:
                with c.cursor() as cursor:require_admin(cursor,args.admin_id,lock=True)
                # MySQL DDL implicitly commits; this CLI requires an authorized
                # operator. Recheck schema completeness with --status afterwards.
                apply_historical_schema(c)
            result={'mode':'schema','status':'applied'}
        elif args.preview is not None or args.publish is not None:
            from src.database.historical import publish_historical
            result=publish_historical(args.preview if args.preview is not None else args.publish,args.admin_id,
                publish=args.publish is not None,connection_factory=connection_factory)
        else:
            candidate=prepare_historical(args.file,sheet=args.sheet)
            result={'mode':'load' if args.load else 'dry_run','source_sha256':candidate.source.sha256,'summary':candidate.summary,
                'audit':candidate.audit,
                'date_findings':dict(Counter(issue for r in candidate.rows for issue in r['date_issues']))}
            if args.load:
                from src.database.historical import load_historical
                result.update(load_historical(candidate,admin_id=args.admin_id,connection_factory=connection_factory))
        print(json.dumps(result,default=str,ensure_ascii=False,indent=2));return 0
    except Exception as error:
        # Source values, credentials, and driver messages must not enter logs.
        print(json.dumps({'status':'failed','message':'Operasi historis gagal; periksa sumber, kandidat, admin, dan skema. Tidak ada detail sensitif dicetak.',
                          'mysql_code':error.args[0] if isinstance(error,pymysql.MySQLError) and isinstance(error.args[0],int) else None}));return 1


if __name__=='__main__':raise SystemExit(main())
