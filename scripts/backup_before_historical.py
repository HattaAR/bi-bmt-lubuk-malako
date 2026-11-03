"""Private verified backup before the explicitly authorized historical migration.

No application users or production data are modified. A newly created temporary
database is used only to verify restoration, then removed. Never prints SQL,
credentials, password hashes, or source records.
"""
import argparse
import difflib
from datetime import datetime,timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def digest_file(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def fingerprint_database(name):
    from src.database.connection import get_connection
    content=hashlib.sha256();schema=hashlib.sha256();counts={};per_table={};definitions={}
    with get_connection(database=name) as connection:
        with connection.cursor() as cursor:
            cursor.execute('START TRANSACTION READ ONLY')
            cursor.execute('SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME')
            tables=cursor.fetchall()
            for row in tables:
                table=row['TABLE_NAME']
                if not re.fullmatch('[a-z0-9_]+',table) or row['ENGINE']!='InnoDB':
                    raise ValueError('Unexpected schema/engine')
                cursor.execute('SELECT * FROM `'+table+'`');rows=cursor.fetchall();counts[table]=len(rows)
                records=sorted(json.dumps(r,sort_keys=True,default=str) for r in rows)
                data=(table+'\n'+'\n'.join(records)).encode();content.update(data)
                cursor.execute('SHOW CREATE TABLE `'+table+'`')
                ddl=cursor.fetchone();definitions[table]=ddl['Create Table']
                # mysqldump restore can make the inherited utf8mb4 charset
                # explicit. Compare that spelling canonically, and ALSO verify
                # the server's actual column metadata below (not just DDL text).
                canonical=re.sub(r' CHARACTER SET utf8mb4(?= COLLATE utf8mb4_)','',ddl['Create Table'])
                definition=canonical.encode();schema.update(definition)
                per_table[table]=dict(content=hashlib.sha256(data).hexdigest(),schema=hashlib.sha256(definition).hexdigest())
            cursor.execute('''SELECT TABLE_NAME,COLUMN_NAME,ORDINAL_POSITION,COLUMN_DEFAULT,IS_NULLABLE,
                COLUMN_TYPE,CHARACTER_SET_NAME,COLLATION_NAME,EXTRA,GENERATION_EXPRESSION,COLUMN_COMMENT
                FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME,ORDINAL_POSITION''')
            columns=cursor.fetchall()
            cursor.execute('''SELECT TABLE_NAME,CONSTRAINT_NAME,COLUMN_NAME,ORDINAL_POSITION,
                REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME,
                CASE WHEN REFERENCED_TABLE_SCHEMA=DATABASE() THEN '<self>' ELSE REFERENCED_TABLE_SCHEMA END AS referenced_schema
                FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE()
                ORDER BY TABLE_NAME,CONSTRAINT_NAME,ORDINAL_POSITION''')
            keys=cursor.fetchall()
        connection.rollback()
    return dict(content_sha256=content.hexdigest(),schema_sha256=schema.hexdigest(),rows=counts,per_table=per_table,
        column_and_key_sha256=hashlib.sha256(json.dumps(dict(columns=columns,keys=keys),sort_keys=True,default=str).encode()).hexdigest(),definitions=definitions)


def private_directory(path):
    path.mkdir(parents=True,exist_ok=False)
    if os.name=='nt':
        sid=subprocess.run(['powershell','-NoProfile','-Command',
            '[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value'],capture_output=True,check=True,text=True).stdout.strip()
        if not re.fullmatch(r'S-1-[0-9-]+',sid):raise ValueError('Invalid Windows identity')
        subprocess.run(['icacls',str(path),'/inheritance:r','/grant:r',
            '*'+sid+':(OI)(CI)F','*S-1-5-18:(OI)(CI)F'],capture_output=True,check=True)
    else:path.chmod(0o700)


def option(value):
    return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','\\r')+'"'


def run(mysqldump):
    from src.database.connection import get_connection
    from scripts.historical_readiness import snapshot
    mysqldump=Path(mysqldump).resolve();client=mysqldump.with_name('mysql.exe')
    if not mysqldump.is_file() or not client.is_file():raise ValueError('MySQL clients unavailable')
    before=snapshot();database=before['database']['name']
    if database!='bi_bmt' or any(t['TABLE_NAME']=='fact_pembiayaan_historis' for t in before['tables']):
        raise ValueError('Expected pre-historical production database')
    with get_connection() as c:
        with c.cursor() as q:
            for table,field in (('ROUTINES','ROUTINE_SCHEMA'),('TRIGGERS','TRIGGER_SCHEMA'),('EVENTS','EVENT_SCHEMA')):
                q.execute('SELECT COUNT(*) AS n FROM information_schema.'+table+' WHERE '+field+'=DATABASE()')
                if q.fetchone()['n']:raise ValueError('Review executable database objects before isolated restore')
    folder=ROOT/'backups'/('historical-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    ignored=subprocess.run(['git','check-ignore','--quiet',str(folder/'bi_bmt.sql.gz')],cwd=ROOT)
    if ignored.returncode!=0:raise ValueError('Backup path must be ignored by Git')
    private_directory(folder)
    (folder/'production-before.json').write_text(json.dumps(before,default=str,indent=2),encoding='utf-8')
    source_before=fingerprint_database(database)
    config=folder/'mysql-client.cnf';raw=folder/'bi_bmt.sql';archive=folder/'bi_bmt.sql.gz'
    verify_db='bi_bmt_test_backup_'+uuid.uuid4().hex
    created=False
    try:
        values={'host':os.environ['DB_HOST'],'port':os.environ['DB_PORT'],'user':os.environ['DB_USER'],
            'password':os.getenv('DB_PASSWORD',''),'protocol':'TCP','default-character-set':'utf8mb4',
            'ssl-mode':'VERIFY_IDENTITY' if os.getenv('DB_SSL_CA','').strip() else 'PREFERRED'}
        if os.getenv('DB_SSL_CA','').strip():values['ssl-ca']=os.environ['DB_SSL_CA']
        config.write_text('[client]\n'+''.join(k+'='+option(v)+'\n' for k,v in values.items()),encoding='utf-8')
        with raw.open('xb') as output:
            result=subprocess.run([str(mysqldump),'--defaults-file='+str(config),
                '--single-transaction','--quick','--routines','--events','--triggers','--hex-blob',
                '--set-gtid-purged=OFF','--no-tablespaces',database],stdout=output,stderr=subprocess.PIPE)
        if result.returncode:raise ValueError('mysqldump failed; backup not verified')
        sql=raw.read_bytes()
        if b'-- Dump completed on ' not in sql:raise ValueError('Dump completion marker missing')
        unsafe=rb'(?im)^\s*(USE\s|CREATE\s+DATABASE|DROP\s+DATABASE|GRANT\s|CREATE\s+USER|ALTER\s+USER|DROP\s+USER|SET\s+@@GLOBAL)'
        if re.search(unsafe,sql):raise ValueError('Unsafe database selection/account statement in dump')
        for table,count in source_before['rows'].items():
            if ('CREATE TABLE `'+table+'`').encode() not in sql:raise ValueError('Missing table definition')
            if count and ('INSERT INTO `'+table+'`').encode() not in sql:raise ValueError('Missing table data')
        if not re.fullmatch(r'bi_bmt_test_backup_[a-f0-9]{32}',verify_db):raise ValueError('Unsafe restore database')
        with get_connection(database='information_schema') as c:
            with c.cursor() as q:q.execute('CREATE DATABASE `'+verify_db+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        created=True
        with raw.open('rb') as input_stream:
            restored=subprocess.run([str(client),'--defaults-file='+str(config),'--binary-mode',
                '--database='+verify_db],stdin=input_stream,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if restored.returncode:raise ValueError('Backup restoration failed')
        restore_fingerprint=fingerprint_database(verify_db)
        compared=('content_sha256','schema_sha256','column_and_key_sha256','rows')
        if any(restore_fingerprint[k]!=source_before[k] for k in compared):
            differences={table:{key:source_before['per_table'][table][key]==restore_fingerprint['per_table'].get(table,{}).get(key)
                for key in ('content','schema')} for table in source_before['rows']}
            (folder/'restore-difference.json').write_text(json.dumps(differences,indent=2),encoding='utf-8')
            print(json.dumps(dict(restore_comparison=differences)))
            ddl_diff={table:list(difflib.unified_diff(source_before['definitions'][table].splitlines(),
                restore_fingerprint['definitions'][table].splitlines())) for table in ('app_users','current_publications','dim_kolektibilitas')}
            print(json.dumps(dict(ddl_differences=ddl_diff)))
            raise ValueError('Restored schema/data fingerprint mismatch')
        if fingerprint_database(database)!=source_before:raise ValueError('Production changed during backup')
        dump_sha=digest_file(raw)
        with raw.open('rb') as input_stream,gzip.open(archive,'xb') as output:shutil.copyfileobj(input_stream,output)
        roundtrip=hashlib.sha256()
        with gzip.open(archive,'rb') as input_stream:
            for block in iter(lambda:input_stream.read(1024*1024),b''):roundtrip.update(block)
        if roundtrip.hexdigest()!=dump_sha:raise ValueError('Compressed backup integrity failed')
        report=dict(database=database,verified=True,restored_data_and_schema_match=True,
            ddl_comparison='Canonical inherited utf8mb4 spelling plus actual information_schema column/key metadata',
            gzip_integrity=True,sql_sha256=dump_sha,archive_sha256=digest_file(archive),
            archive_bytes=archive.stat().st_size,table_rows=source_before['rows'],
            production_unchanged=True,restore_database_removed=False,temporary_credentials_removed=False)
    finally:
        if created:
            with get_connection(database='information_schema') as c:
                with c.cursor() as q:q.execute('DROP DATABASE `'+verify_db+'`')
        if config.exists():config.unlink()
    report['restore_database_removed']=True;report['temporary_credentials_removed']=True
    (folder/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    raw.unlink() # Only the verified gzip backup is retained, in the private directory.
    print(json.dumps(dict(backup=str(archive.relative_to(ROOT)),verification=str((folder/'verification.json').relative_to(ROOT)),
        restored_data_and_schema_match=True,production_unchanged=True,temporary_credentials_removed=True)))
    return folder


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mysqldump',required=True)
    args=p.parse_args()
    try:run(args.mysqldump)
    except Exception as error:
        safe_messages={'MySQL clients unavailable','Expected pre-historical production database',
            'Review executable database objects before isolated restore','Backup path must be ignored by Git',
            'Invalid Windows identity','mysqldump failed; backup not verified','Dump completion marker missing',
            'Unsafe database selection/account statement in dump','Missing table definition','Missing table data',
            'Unsafe restore database','Backup restoration failed','Restored schema/data fingerprint mismatch',
            'Production changed during backup','Compressed backup integrity failed','Unexpected schema/engine'}
        print(json.dumps(dict(status='backup_failed',error_type=type(error).__name__,
            check=str(error) if str(error) in safe_messages else 'Private verification step failed',
            historical_migration_or_load_attempted=False)))
        raise SystemExit(1)
