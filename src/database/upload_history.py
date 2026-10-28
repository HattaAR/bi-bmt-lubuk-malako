"""Read-only financing-version history. No file reads, ETL, or publication writes."""
from contextlib import contextmanager
import json
import re
from src.database.connection import get_connection
from src.database.active_portfolio import current_active_publication

KINDS=('active','historical','transactions')
STATUSES=('draft','validating','invalid','ready','published','current','previous')
SORTS={'uploaded_desc':'m.uploaded_at IS NULL,m.uploaded_at DESC,d.created_at DESC,d.dataset_version_id DESC',
       'uploaded_asc':'m.uploaded_at IS NULL,m.uploaded_at ASC,d.created_at ASC,d.dataset_version_id ASC',
       'name_asc':'d.report_name ASC,d.dataset_version_id ASC'}

MAIN='''WITH main_sources AS (
    SELECT ds.dataset_version_id,COUNT(DISTINCT s.source_file_id) AS file_count,
        GROUP_CONCAT(DISTINCT s.original_filename ORDER BY s.original_filename SEPARATOR ' · ') AS filenames,
        MIN(s.uploaded_at) AS uploaded_at,
        GROUP_CONCAT(DISTINCT u.display_name ORDER BY u.display_name SEPARATOR ' · ') AS uploaders
    FROM dataset_sources ds JOIN source_files s USING(source_file_id)
    JOIN dataset_versions v ON v.dataset_version_id=ds.dataset_version_id
    LEFT JOIN app_users u ON u.user_id=s.uploaded_by
    WHERE v.dataset_kind IN ('active','historical','transactions') AND ds.source_role<>'reference_dictionary'
    GROUP BY ds.dataset_version_id)
'''
JOIN=''' FROM dataset_versions d LEFT JOIN main_sources m USING(dataset_version_id)
    LEFT JOIN dataset_publications p ON p.dataset_version_id=d.dataset_version_id
    LEFT JOIN current_publications cp ON cp.publication_id=p.publication_id AND cp.dataset_kind=d.dataset_kind
'''
COLUMNS='''d.dataset_version_id,d.dataset_kind,d.report_name,d.status,d.created_at,
    d.position_date,d.position_date_status,d.export_date,d.export_period_text,
    COALESCE(m.file_count,0) AS file_count,m.filenames,m.uploaded_at,m.uploaders,
    p.publication_id,p.published_at,p.reference_dataset_version_id,cp.publication_id IS NOT NULL AS is_current'''


@contextmanager
def _snapshot(factory):
    connection=factory()
    try:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            cursor.execute('START TRANSACTION READ ONLY')
            yield cursor
    finally:
        try:connection.rollback()
        finally:connection.close()


def _current(cursor):
    # Reuse the active reader's consistency checks, including dictionary status.
    active=current_active_publication(cursor)
    cursor.execute('''SELECT cp.dataset_kind AS pointer_kind,cp.publication_id,d.dataset_version_id,
        d.dataset_kind,d.report_name,d.status,d.position_date,d.position_date_status,p.published_at
        FROM current_publications cp LEFT JOIN dataset_publications p USING(publication_id)
        LEFT JOIN dataset_versions d ON d.dataset_version_id=p.dataset_version_id
        WHERE cp.dataset_kind IN ('active','historical','transactions')''')
    result={kind:None for kind in KINDS}
    for row in cursor.fetchall():
        kind=row.pop('pointer_kind')
        if not row['dataset_version_id'] or row['dataset_kind']!=kind or row['status']!='published':
            raise ValueError('Pointer publikasi tidak konsisten; tidak memilih kandidat pengganti.')
        result[kind]=row
    if (active is None)!=(result['active'] is None):raise ValueError('Snapshot pointer aktif tidak konsisten.')
    return result


def _filters(search,kind,status):
    if not isinstance(search,str) or len(search)>180:raise ValueError('Pencarian maksimal 180 karakter.')
    if kind is not None and kind not in KINDS:raise ValueError('Jenis riwayat tidak didukung.')
    if status is not None and status not in STATUSES:raise ValueError('Status riwayat tidak didukung.')
    clauses=["d.dataset_kind IN ('active','historical','transactions')"];parameters=[]
    if kind:clauses.append('d.dataset_kind=%s');parameters.append(kind)
    if status=='current':clauses.append('cp.publication_id IS NOT NULL')
    elif status=='previous':clauses.append('p.publication_id IS NOT NULL AND cp.publication_id IS NULL')
    elif status=='published':clauses.append('p.publication_id IS NOT NULL')
    elif status:
        clauses.append('d.status=%s AND p.publication_id IS NULL');parameters.append(status)
    search=search.strip()
    if search:
        literal='%'+search.replace('!','!!').replace('%','!%').replace('_','!_')+'%'
        clauses.append("""(d.report_name LIKE %s ESCAPE '!' OR EXISTS (
            SELECT 1 FROM dataset_sources xs JOIN source_files xf USING(source_file_id)
            WHERE xs.dataset_version_id=d.dataset_version_id AND xs.source_role<>'reference_dictionary'
            AND xf.original_filename LIKE %s ESCAPE '!'))""")
        parameters.extend((literal,literal))
    return ' WHERE '+' AND '.join(clauses),parameters


def get_upload_history(*,search='',kind=None,status=None,sort='uploaded_desc',page=1,page_size=10,connection_factory=get_connection):
    if sort not in SORTS or type(page) is not int or page<1 or type(page_size) is not int or page_size not in (5,10,25,50):
        raise ValueError('Urutan/pagination tidak valid.')
    where,args=_filters(search,kind,status)
    with _snapshot(connection_factory) as cursor:
        current=_current(cursor)
        cursor.execute(MAIN+'''SELECT COUNT(*) AS total,
            COALESCE(SUM(d.status='ready' AND p.publication_id IS NULL),0) AS ready,
            COALESCE(SUM(p.publication_id IS NOT NULL),0) AS published,
            COALESCE(SUM(cp.publication_id IS NOT NULL),0) AS current,
            COALESCE(SUM(d.status='invalid'),0) AS invalid
            '''+JOIN+where,args)
        summary={k:int(v) for k,v in cursor.fetchone().items()}
        pages=max(1,(summary['total']+page_size-1)//page_size);page=min(page,pages)
        cursor.execute(MAIN+'SELECT '+COLUMNS+JOIN+where+' ORDER BY '+SORTS[sort]+' LIMIT %s OFFSET %s',(*args,page_size,(page-1)*page_size))
        rows=list(cursor.fetchall())
        for row in rows:row['is_current']=bool(row['is_current'])
        return dict(rows=rows,summary=summary,current=current,page=page,pages=pages,page_size=page_size,
                    filters=dict(search=search,kind=kind,status=status,sort=sort))


def _safe_message(message):
    try:
        value=json.loads(message)
        if isinstance(value,dict):message=value.get('reason') or 'Nilai mentah disimpan pada lineage; tidak ditampilkan di riwayat.'
    except (ValueError,TypeError):pass
    # Do not expose arbitrary raw account identifiers through stored messages.
    return re.sub(r'\d{6,}','[pengenal disamarkan]',str(message))[:1000]


def _control(message):
    try:
        value=json.loads(message)
        allowed=('rows','unique_accounts','totals','collectibility','unmapped_marketing','unmapped_sector')
        summary={k:value[k] for k in allowed if k in value}
        # Stored control is not a fresh reconciliation; retain recorded values.
        return summary
    except (ValueError,TypeError):return None


def get_upload_detail(dataset_id,*,connection_factory=get_connection):
    if type(dataset_id) is not int or dataset_id<=0:raise ValueError('ID riwayat tidak valid.')
    with _snapshot(connection_factory) as cursor:
        current=_current(cursor)
        cursor.execute(MAIN+'SELECT '+COLUMNS+''',d.scope_description,d.schema_version,d.mapping_version,d.validation_rule_version
            '''+JOIN+" WHERE d.dataset_version_id=%s AND d.dataset_kind IN ('active','historical','transactions')",(dataset_id,))
        version=cursor.fetchone()
        if not version:raise ValueError('Versi pembiayaan tidak ditemukan.')
        version['is_current']=bool(version['is_current'])
        cursor.execute('''SELECT s.source_file_id,s.original_filename,s.file_sha256,s.byte_size,s.uploaded_at,
            u.display_name AS uploaded_by,ds.source_role,ds.sheet_name FROM dataset_sources ds
            JOIN source_files s USING(source_file_id) LEFT JOIN app_users u ON u.user_id=s.uploaded_by
            WHERE ds.dataset_version_id=%s ORDER BY ds.source_role,s.source_file_id,ds.sheet_name''',(dataset_id,))
        sources=list(cursor.fetchall())
        cursor.execute('''SELECT severity,COUNT(*) AS n FROM validation_findings WHERE dataset_version_id=%s GROUP BY severity''',(dataset_id,))
        counts=dict(blocking=0,warning=0,information=0)
        counts.update({r['severity']:r['n'] for r in cursor.fetchall()})
        cursor.execute('''SELECT rule_code,severity,source_row_number,field_name,message,affected_function,created_at
            FROM validation_findings WHERE dataset_version_id=%s AND rule_code<>'RECONCILIATION_PASSED'
            ORDER BY FIELD(severity,'blocking','warning','information'),finding_id LIMIT 100''',(dataset_id,))
        findings=list(cursor.fetchall())
        for finding in findings:finding['message']=_safe_message(finding['message'])
        cursor.execute('''SELECT rule_code,message,created_at FROM validation_findings
            WHERE dataset_version_id=%s AND rule_code='RECONCILIATION_PASSED' AND severity='information' ORDER BY finding_id''',(dataset_id,))
        reconciliation=[dict(rule_code=r['rule_code'],summary=_control(r['message']),created_at=r['created_at']) for r in cursor.fetchall()]
        cursor.execute('''SELECT p.publication_id,p.reference_dataset_version_id,p.published_at,p.previous_publication_id,
            u.display_name AS published_by,cp.publication_id IS NOT NULL AS is_current
            FROM dataset_publications p LEFT JOIN app_users u ON u.user_id=p.published_by
            LEFT JOIN current_publications cp ON cp.publication_id=p.publication_id AND cp.dataset_kind=%s
            WHERE p.dataset_version_id=%s''',(version['dataset_kind'],dataset_id))
        publication=cursor.fetchone()
        return dict(version=version,sources=sources,findings=findings,finding_counts=counts,
                    reconciliation=reconciliation,publication=publication,current=current,findings_limit=100)
