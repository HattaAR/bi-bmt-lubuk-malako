"""Read-only before/after evidence for the authorized historical candidate load."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'docs/screenshots/historical-production-load'
MUTABLE={'dataset_versions','dataset_sources','source_files','validation_findings'}


def digest(rows):
    return hashlib.sha256('\n'.join(sorted(json.dumps(r,sort_keys=True,default=str) for r in rows)).encode()).hexdigest()


def state(baseline=None):
    from src.database.connection import get_connection
    tables={};metadata_new={}
    with get_connection() as c:
        with c.cursor() as q:
            q.execute('START TRANSACTION READ ONLY')
            q.execute('SELECT DATABASE() AS name');assert q.fetchone()['name']=='bi_bmt'
            q.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME')
            names=[r['TABLE_NAME'] for r in q.fetchall()]
            for name in names:
                if not re.fullmatch('[a-z0-9_]+',name):raise ValueError('Unexpected table')
                q.execute('''SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND CONSTRAINT_NAME='PRIMARY' ORDER BY ORDINAL_POSITION''',(name,))
                keys=[r['COLUMN_NAME'] for r in q.fetchall()]
                if not keys:raise ValueError('Primary key required')
                q.execute('SELECT * FROM `'+name+'`');rows=q.fetchall()
                ids=[tuple(r[k] for k in keys) for r in rows]
                q.execute('SHOW CREATE TABLE `'+name+'`')
                ddl=re.sub(r' AUTO_INCREMENT=\d+','',q.fetchone()['Create Table'])
                table=dict(count=len(rows),keys=keys,ids=ids,content=digest(rows),ddl_sha256=hashlib.sha256(ddl.encode()).hexdigest())
                if baseline and name in baseline['tables']:
                    old={tuple(i) for i in baseline['tables'][name]['ids']}
                    table['old_content']=digest([r for r in rows if tuple(r[k] for k in keys) in old])
                    if name in MUTABLE:metadata_new[name]=[r for r in rows if tuple(r[k] for k in keys) not in old]
                tables[name]=table
            q.execute('SELECT TRIGGER_NAME,EVENT_OBJECT_TABLE FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE() ORDER BY TRIGGER_NAME')
            triggers=q.fetchall()
        c.rollback()
    raw={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'data/raw').rglob('*') if p.is_file()}
    return dict(tables=tables,triggers=triggers,raw=raw,dev=hashlib.sha256((ROOT/'dev.cmd').read_bytes()).hexdigest()),metadata_new


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=('before','after'));p.add_argument('--candidate',type=int)
    args=p.parse_args();OUT.mkdir(parents=True,exist_ok=True);file=OUT/'protected-before.json'
    if args.phase=='before':
        if file.exists():raise ValueError('Baseline already exists; do not overwrite')
        before,_=state();assert 'fact_pembiayaan_historis' not in before['tables']
        file.write_text(json.dumps(before,indent=2),encoding='utf-8')
        print(json.dumps(dict(baseline_saved=True,tables=len(before['tables']))));return
    if not args.candidate:raise ValueError('Candidate ID required')
    before=json.loads(file.read_text(encoding='utf-8'));after,new=state(before)
    checks={name:dict(existing_rows_unchanged=after['tables'][name]['old_content']==t['content'],
        schema_unchanged=after['tables'][name]['ddl_sha256']==t['ddl_sha256'],
        no_extra_rows=name in MUTABLE or after['tables'][name]['content']==t['content']) for name,t in before['tables'].items()}
    assert all(all(c.values()) for c in checks.values())
    assert set(after['tables'])-set(before['tables'])=={'fact_pembiayaan_historis'}
    expected={'protect_historical_insert','protect_historical_update','protect_historical_delete'}
    assert {r['TRIGGER_NAME'] for r in after['triggers']}==expected
    assert all(r['EVENT_OBJECT_TABLE']=='fact_pembiayaan_historis' for r in after['triggers'])
    assert all(r['dataset_version_id']==args.candidate for n in ('dataset_versions','dataset_sources','validation_findings') for r in new[n])
    assert len(new['dataset_versions'])==1 and len(new['dataset_sources'])==1 and len(new['validation_findings'])==89
    source_id=new['dataset_sources'][0]['source_file_id']
    assert len(new['source_files'])<=1 and all(r['source_file_id']==source_id for r in new['source_files'])
    assert after['raw']==before['raw'] and after['dev']==before['dev']
    report=dict(candidate=args.candidate,protected_tables=checks,only_expected_historical_additions=True,
        metadata_added={n:len(r) for n,r in new.items()},raw_and_dev_unchanged=True,
        new_table='fact_pembiayaan_historis',new_triggers=sorted(expected))
    (OUT/'protected-after.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(candidate=args.candidate,all_protected_tables_unchanged=True,
        only_expected_historical_additions=True,metadata_added=report['metadata_added'],raw_and_dev_unchanged=True)))


if __name__=='__main__':main()
