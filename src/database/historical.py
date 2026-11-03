"""Versioned historical candidates/publications; no DDL or active data changes."""
import json
from decimal import Decimal
from src.database.connection import get_connection
from src.database.active_candidates import active_write_transaction,_insert,_source_id
from src.database.publication_checks import require_admin
from src.etl.historical import VERSION,historical_digest,HistoricalCandidate,identical_rows_decision


def require_historical_storage(cursor):
    cursor.execute("SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='fact_pembiayaan_historis'")
    table=cursor.fetchone()
    cursor.execute("SELECT TRIGGER_NAME FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE() AND EVENT_OBJECT_TABLE='fact_pembiayaan_historis'")
    triggers={r['TRIGGER_NAME'] for r in cursor.fetchall()}
    if not table or table['ENGINE']!='InnoDB' or not {'protect_historical_insert','protect_historical_update','protect_historical_delete'}<=triggers:
        raise ValueError('Skema/perlindungan historis belum lengkap; periksa status migrasi.')


def verify_manifest(cursor,dataset_id,expected):
    """Aggregate reconciliation alone cannot detect swapped dates/raw lineage."""
    cursor.execute('''SELECT source_file_id,source_sheet,source_row_number,realization_date,original_maturity_date,
        completion_date,original_principal,contract_duration_days,eligible,target_late,completion_delay_days,
        date_issues,raw_values FROM fact_pembiayaan_historis WHERE dataset_version_id=%s''',(dataset_id,))
    rows=list(cursor.fetchall())
    for row in rows:
        for key in ('date_issues','raw_values'):row[key]=json.loads(row[key])
    if historical_digest(rows)!=expected['facts_sha256']:raise ValueError('Lineage/fakta historis tidak cocok.')
    audit=HistoricalCandidate(None,sorted(rows,key=lambda r:r['source_row_number'])).audit
    for key in ('duplicate_groups','duplicate_group_count','duplicate_extra_records','identical_records','unique_contracts'):
        if audit[key]!=expected['audit'][key]:raise ValueError('Audit baris identik tidak cocok.')
    if expected['audit']['identical_rows_decision']!=identical_rows_decision(expected['source']):
        raise ValueError('Keputusan bisnis historis tidak cocok dengan sumber/aturan saat ini.')
    cursor.execute('''SELECT ds.source_file_id,ds.sheet_name,s.file_sha256,s.byte_size FROM dataset_sources ds
        JOIN source_files s USING(source_file_id) WHERE ds.dataset_version_id=%s AND ds.source_role=%s''',(dataset_id,'historical_main'))
    sources=cursor.fetchall()
    if len(sources)!=1:raise ValueError('Hubungan sumber historis tidak konsisten.')
    source=sources[0]
    if (source['sheet_name']!=expected['source']['sheet'] or source['file_sha256']!=expected['source']['sha256']
            or source['byte_size']!=expected['source']['byte_size']
            or any(r['source_file_id']!=source['source_file_id'] or r['source_sheet']!=source['sheet_name'] for r in rows)):
        raise ValueError('Sumber historis tidak cocok.')
    cursor.execute('''SELECT source_file_id,source_row_number,rule_code,severity FROM validation_findings
        WHERE dataset_version_id=%s ORDER BY source_row_number,rule_code''',(dataset_id,))
    findings=cursor.fetchall()
    actual=[{k:r[k] for k in ('source_row_number','rule_code','severity')} for r in findings]
    if (any(r['source_file_id']!=source['source_file_id'] for r in findings)
            or actual!=expected['findings']):raise ValueError('Temuan wajib historis tidak cocok.')


def stored_summary(cursor,dataset_id):
    cursor.execute('''SELECT COUNT(*) AS rows_count,COALESCE(SUM(eligible),0) AS eligible,
        COALESCE(SUM(target_late=1),0) AS late,COALESCE(SUM(original_principal),0) AS original_principal,
        COALESCE(SUM(original_principal IS NULL),0) AS invalid_nominal
        FROM fact_pembiayaan_historis WHERE dataset_version_id=%s''',(dataset_id,))
    row=cursor.fetchone();row['rows']=row.pop('rows_count');return row


def load_historical(candidate,*,admin_id=None,connection_factory=get_connection):
    candidate.verify_source()
    with active_write_transaction(connection_factory=connection_factory) as cursor:
        require_admin(cursor,admin_id,lock=True)
        require_historical_storage(cursor)
        name='historical-candidate:'+candidate.key
        cursor.execute('SELECT dataset_version_id,status FROM dataset_versions WHERE dataset_kind=%s AND BINARY report_name=BINARY %s',('historical',name))
        previous=cursor.fetchall()
        if len(previous)>1:raise ValueError('Identitas historis ganda.')
        if previous:
            d=previous[0]
            if d['status'] not in ('ready','published') or stored_summary(cursor,d['dataset_version_id'])!=candidate.summary:raise ValueError('Kandidat existing tidak konsisten; tidak ditimpa.')
            inspect_historical(cursor,d['dataset_version_id'],admin_id)
            return {**d,'reused':True}
        source_id=_source_id(cursor,candidate.source,uploaded_by=admin_id)
        summary=candidate.summary
        audit=candidate.audit
        identical={line for group in audit['duplicate_groups'] for line in group}
        identical_rule=('identical_values_distinct_records' if audit['identical_rows_decision'] else 'potential_exact_duplicate')
        findings=[]
        for row in candidate.rows:
            rules=row['date_issues']+(['invalid_nominal'] if row['original_principal'] is None else [])
            if row['source_row_number'] in identical:rules=rules+[identical_rule]
            findings.extend(dict(source_row_number=row['source_row_number'],rule_code='historical_'+rule,severity='warning') for rule in rules)
        findings.sort(key=lambda r:(r['source_row_number'],r['rule_code']))
        manifest=dict(summary,audit=audit,facts_sha256=historical_digest(candidate.rows),findings=findings,
                      source=dict(candidate.source.identity(),byte_size=candidate.source.byte_size))
        dataset=_insert(cursor,'dataset_versions',dict(dataset_kind='historical',report_name=name,schema_version=VERSION,
            mapping_version=VERSION,validation_rule_version=VERSION,status='validating',scope_description=json.dumps(manifest,default=str)))
        _insert(cursor,'dataset_sources',dict(dataset_version_id=dataset,source_file_id=source_id,source_role='historical_main',sheet_name=candidate.source.sheet))
        for row in candidate.rows:
            values={k:row[k] for k in ('realization_date','original_maturity_date','completion_date','original_principal','contract_duration_days','eligible','target_late','completion_delay_days')}
            _insert(cursor,'fact_pembiayaan_historis',dict(dataset_version_id=dataset,source_file_id=source_id,source_sheet=candidate.source.sheet,
                source_row_number=row['source_row_number'],**values,date_issues=json.dumps(row['date_issues']),raw_values=json.dumps(row['raw_values'],default=str)))
        for finding in findings:
            if finding['rule_code']=='historical_identical_values_distinct_records':
                message='Catatan audit: BMT mengonfirmasi pembiayaan berbeda dengan nilai identik. Semua record dan lineage dipertahankan; ID kontrak sumber tidak tersedia.'
            elif finding['rule_code']=='historical_potential_exact_duplicate':
                message='Dugaan baris identik; seluruh record dipertahankan. Identitas kontrak belum terverifikasi; menunggu keputusan BMT.'
            else:message='Nilai sumber dipertahankan; lihat lineage fakta.'
            _insert(cursor,'validation_findings',dict(dataset_version_id=dataset,source_file_id=source_id,**finding,
                message=message,affected_function='historical_analysis'))
        if stored_summary(cursor,dataset)!=summary:raise ValueError('Rekonsiliasi historis gagal.')
        verify_manifest(cursor,dataset,manifest)
        candidate.verify_source()
        status='ready' if summary['eligible'] else 'invalid'
        cursor.execute('UPDATE dataset_versions SET status=%s WHERE dataset_version_id=%s',(status,dataset))
        return dict(dataset_version_id=dataset,status=status,reused=False)


def inspect_historical(cursor,dataset_id,admin_id=None):
    require_historical_storage(cursor)
    cursor.execute('SELECT * FROM dataset_versions WHERE dataset_version_id=%s',(dataset_id,));version=cursor.fetchone()
    if not version or version['dataset_kind']!='historical' or version['status'] not in ('ready','published') or version['validation_rule_version']!=VERSION:raise ValueError('Kandidat historis belum siap.')
    summary=stored_summary(cursor,dataset_id);expected=json.loads(version['scope_description'])
    if any(Decimal(str(summary[k]))!=Decimal(str(expected[k])) for k in summary):raise ValueError('Rekonsiliasi historis tidak cocok.')
    if not summary['eligible']:raise ValueError('Tidak ada tanggal historis yang layak dianalisis.')
    require_admin(cursor,admin_id,lock=True)
    verify_manifest(cursor,dataset_id,expected)
    cursor.execute("SELECT cp.publication_id FROM current_publications cp WHERE dataset_kind='historical' FOR UPDATE")
    previous=cursor.fetchone()
    return dict(dataset_version_id=dataset_id,status=version['status'],summary=summary,audit=expected['audit'],
        warnings=len(expected['findings']),source=expected['source'],reconciliation='passed',
        previous_publication_id=previous['publication_id'] if previous else None)


def publish_historical(dataset_id,admin_id,*,publish=False,connection_factory=get_connection):
    with active_write_transaction(connection_factory=connection_factory) as cursor:
        result=inspect_historical(cursor,dataset_id,admin_id)
        cursor.execute('SELECT publication_id FROM dataset_publications WHERE dataset_version_id=%s',(dataset_id,));existing=cursor.fetchone()
        if existing:return {**result,**existing,'reused':True}
        decision=result['audit']['identical_rows_decision']
        can_publish=not result['audit']['duplicate_groups'] or bool(decision and decision['retain_all_records'])
        if not publish:return {**result,'can_publish':can_publish,'technical_ready':True,'mode':'preview',
            'publication_blocker':None if can_publish else 'awaiting_bmt_identical_rows'}
        if not can_publish:raise ValueError('Publikasi ditahan: keputusan BMT tentang baris identik belum tersedia.')
        identifier=_insert(cursor,'dataset_publications',dict(dataset_version_id=dataset_id,published_by=admin_id,previous_publication_id=result['previous_publication_id']))
        cursor.execute("UPDATE dataset_versions SET status='published' WHERE dataset_version_id=%s",(dataset_id,))
        cursor.execute("INSERT INTO current_publications(dataset_kind,publication_id) VALUES('historical',%s) ON DUPLICATE KEY UPDATE publication_id=%s",(identifier,identifier))
        return {**result,'status':'published','publication_id':identifier,'reused':False}
