"""Read-only production/raw baseline; never emits source records or secrets."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'docs/screenshots/historical-readiness'

def snapshot():
    from src.database.connection import get_connection
    content=hashlib.sha256();schema=hashlib.sha256()
    with get_connection() as c:
        c.rollback()
        with c.cursor() as q:
            q.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            q.execute('START TRANSACTION READ ONLY')
            q.execute('SELECT DATABASE() AS name,VERSION() AS version');db=q.fetchone()
            q.execute('SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME')
            tables=q.fetchall()
            for row in tables:
                name=row['TABLE_NAME']
                if not re.fullmatch('[a-z0-9_]+',name):raise ValueError('Unexpected table name')
                q.execute('SELECT * FROM '+name)
                data=sorted(json.dumps(v,sort_keys=True,default=str) for v in q.fetchall())
                content.update((name+'\n'+'\n'.join(data)).encode())
                q.execute('SHOW CREATE TABLE '+name)
                schema.update(json.dumps(q.fetchone(),sort_keys=True,default=str).encode())
            q.execute('SELECT TRIGGER_NAME,ACTION_STATEMENT FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE() ORDER BY TRIGGER_NAME')
            schema.update(json.dumps(q.fetchall(),sort_keys=True,default=str).encode())
            q.execute('SELECT cp.dataset_kind,cp.publication_id,p.dataset_version_id,p.reference_dataset_version_id FROM current_publications cp JOIN dataset_publications p USING(publication_id) ORDER BY cp.dataset_kind')
            pointers=q.fetchall()
            q.execute("SELECT dataset_kind,status,COUNT(*) AS versions FROM dataset_versions GROUP BY dataset_kind,status ORDER BY dataset_kind,status")
            versions=q.fetchall()
            q.execute("SELECT u.user_id FROM app_users u JOIN app_user_roles r USING(user_id) WHERE u.is_active=1 AND r.role_code='admin' ORDER BY u.user_id")
            admins=[r['user_id'] for r in q.fetchall()]
        c.rollback()
    raw={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'data/raw').rglob('*') if p.is_file()}
    return dict(database=db,tables=tables,pointers=pointers,versions=versions,active_admin_ids=admins,
                content_sha256=content.hexdigest(),schema_sha256=schema.hexdigest(),raw_sha256=raw,
                dev_sha256=hashlib.sha256((ROOT/'dev.cmd').read_bytes()).hexdigest())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['before','after'])
    phase=p.parse_args().phase;OUT.mkdir(parents=True,exist_ok=True)
    current=snapshot()
    if phase=='before':
        if (OUT/'integrity-before.json').exists():raise ValueError('Baseline already exists')
        (OUT/'integrity-before.json').write_text(json.dumps(current,indent=2,default=str))
        print(json.dumps({k:current[k] for k in ('database','tables','pointers','versions','active_admin_ids')},default=str))
    else:
        old=json.loads((OUT/'integrity-before.json').read_text())
        checks={k:current[k]==old[k] for k in ('content_sha256','schema_sha256','raw_sha256','dev_sha256')}
        (OUT/'integrity-after.json').write_text(json.dumps(checks,indent=2))
        print(json.dumps(checks));assert all(checks.values())
