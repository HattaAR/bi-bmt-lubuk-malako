"""Versioned historical candidates/publications; no DDL or active data changes."""
import json
from decimal import Decimal
from src.database.connection import get_connection
from src.database.active_candidates import active_write_transaction,_insert,_source_id
from src.database.publication_checks import require_admin
from src.etl.historical import VERSION


def stored_summary(cursor,dataset_id):
    cursor.execute('''SELECT COUNT(*) AS rows_count,COALESCE(SUM(eligible),0) AS eligible,
        COALESCE(SUM(target_late=1),0) AS late,COALESCE(SUM(original_principal),0) AS original_principal,
        COALESCE(SUM(original_principal IS NULL),0) AS invalid_nominal
        FROM fact_pembiayaan_historis WHERE dataset_version_id=%s''',(dataset_id,))
    row=cursor.fetchone();row['rows']=row.pop('rows_count');return row


def load_historical(candidate,*,connection_factory=get_connection):
    candidate.verify_source()
    with active_write_transaction(connection_factory=connection_factory) as cursor:
        name='historical-candidate:'+candidate.key
        cursor.execute('SELECT dataset_version_id,status FROM dataset_versions WHERE dataset_kind=%s AND BINARY report_name=BINARY %s',('historical',name))
        previous=cursor.fetchall()
        if len(previous)>1:raise ValueError('Identitas historis ganda.')
        if previous:
            d=previous[0]
            if d['status'] not in ('ready','published') or stored_summary(cursor,d['dataset_version_id'])!=candidate.summary:raise ValueError('Kandidat existing tidak konsisten; tidak ditimpa.')
            return {**d,'reused':True}
        source_id=_source_id(cursor,candidate.source)
        summary=candidate.summary
        dataset=_insert(cursor,'dataset_versions',dict(dataset_kind='historical',report_name=name,schema_version=VERSION,
            mapping_version=VERSION,validation_rule_version=VERSION,status='validating',scope_description=json.dumps(summary,default=str)))
        _insert(cursor,'dataset_sources',dict(dataset_version_id=dataset,source_file_id=source_id,source_role='historical_main',sheet_name=candidate.source.sheet))
        for row in candidate.rows:
            values={k:row[k] for k in ('realization_date','original_maturity_date','completion_date','original_principal','contract_duration_days','eligible','target_late','completion_delay_days')}
            _insert(cursor,'fact_pembiayaan_historis',dict(dataset_version_id=dataset,source_file_id=source_id,source_sheet=candidate.source.sheet,
                source_row_number=row['source_row_number'],**values,date_issues=json.dumps(row['date_issues']),raw_values=json.dumps(row['raw_values'],default=str)))
            for rule in row['date_issues']+(['invalid_nominal'] if row['original_principal'] is None else []):
                _insert(cursor,'validation_findings',dict(dataset_version_id=dataset,source_file_id=source_id,source_row_number=row['source_row_number'],
                    rule_code='historical_'+rule,severity='warning',message='Nilai sumber dipertahankan; lihat lineage fakta.',affected_function='historical_analysis'))
        if stored_summary(cursor,dataset)!=summary:raise ValueError('Rekonsiliasi historis gagal.')
        candidate.verify_source()
        status='ready' if summary['eligible'] else 'invalid'
        cursor.execute('UPDATE dataset_versions SET status=%s WHERE dataset_version_id=%s',(status,dataset))
        return dict(dataset_version_id=dataset,status=status,reused=False)


def inspect_historical(cursor,dataset_id,admin_id=None):
    cursor.execute('SELECT * FROM dataset_versions WHERE dataset_version_id=%s',(dataset_id,));version=cursor.fetchone()
    if not version or version['dataset_kind']!='historical' or version['status'] not in ('ready','published') or version['validation_rule_version']!=VERSION:raise ValueError('Kandidat historis belum siap.')
    summary=stored_summary(cursor,dataset_id);expected=json.loads(version['scope_description'])
    if any(Decimal(str(summary[k]))!=Decimal(str(expected[k])) for k in summary):raise ValueError('Rekonsiliasi historis tidak cocok.')
    if not summary['eligible']:raise ValueError('Tidak ada tanggal historis yang layak dianalisis.')
    require_admin(cursor,admin_id,lock=True)
    cursor.execute("SELECT cp.publication_id FROM current_publications cp WHERE dataset_kind='historical' FOR UPDATE")
    previous=cursor.fetchone()
    return dict(dataset_version_id=dataset_id,status=version['status'],summary=summary,previous_publication_id=previous['publication_id'] if previous else None)


def publish_historical(dataset_id,admin_id,*,publish=False,connection_factory=get_connection):
    with active_write_transaction(connection_factory=connection_factory) as cursor:
        result=inspect_historical(cursor,dataset_id,admin_id)
        cursor.execute('SELECT publication_id FROM dataset_publications WHERE dataset_version_id=%s',(dataset_id,));existing=cursor.fetchone()
        if existing:return {**result,**existing,'reused':True}
        if not publish:return {**result,'can_publish':True,'mode':'preview'}
        identifier=_insert(cursor,'dataset_publications',dict(dataset_version_id=dataset_id,published_by=admin_id,previous_publication_id=result['previous_publication_id']))
        cursor.execute("UPDATE dataset_versions SET status='published' WHERE dataset_version_id=%s",(dataset_id,))
        cursor.execute("INSERT INTO current_publications(dataset_kind,publication_id) VALUES('historical',%s) ON DUPLICATE KEY UPDATE publication_id=%s",(identifier,identifier))
        return {**result,'status':'published','publication_id':identifier,'reused':False}
