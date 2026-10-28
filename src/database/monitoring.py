"""Published monitoring list/detail, one read-only snapshot per request."""
import re
from decimal import Decimal
from src.database.active_portfolio import current_active_publication
from src.database.active_kpis import _validate_id, _dashboard_context, KPIDataError
from src.database.connection import get_connection
from src.database.active_review import financing_code, review_reason

VALID_MATURITY = 'CASE WHEN t.full_date<r.full_date THEN NULL ELSE t.full_date END'
ORDERS = {
    'arrears_desc':'f.overdue_principal DESC,f.outstanding_principal DESC,f.active_fact_id ASC',
    'outstanding_desc':'f.outstanding_principal DESC,f.overdue_principal DESC,f.active_fact_id ASC',
    'maturity_asc':f'({VALID_MATURITY} IS NULL) ASC,{VALID_MATURITY} ASC,f.overdue_principal DESC,f.active_fact_id ASC',
    'maturity_desc':f'({VALID_MATURITY} IS NULL) ASC,{VALID_MATURITY} DESC,f.overdue_principal DESC,f.active_fact_id ASC',
}
CATEGORY = "CASE WHEN c.collectibility_code IN ('L','KL','D','M') THEN c.collectibility_code ELSE 'UNKNOWN' END"
JOINS = """FROM fact_pembiayaan_aktif f
 LEFT JOIN dim_marketing m ON f.marketing_id=m.marketing_id
 LEFT JOIN dim_sektor s ON f.sector_id=s.sector_id
 LEFT JOIN dim_kolektibilitas c ON f.collectibility_id=c.collectibility_id
 LEFT JOIN dim_tanggal t ON f.maturity_date_key=t.date_key
 LEFT JOIN dim_tanggal r ON f.realization_date_key=r.date_key"""
FIELDS = """f.active_fact_id,f.marketing_id,f.sector_id,m.marketing_name,s.sector_name,
 f.original_principal,f.outstanding_principal,f.overdue_principal,
 f.remaining_margin,f.recorded_tenor,f.installment_unit_code,f.contract_type_code,
 f.financing_type_code,f.financing_subtype_code,f.contract_duration_days,f.model_input_status,
 t.full_date AS maturity_date,r.full_date AS realization_date,
 f.source_sheet,f.source_row_number,""" + CATEGORY + " AS collectibility_code"


def _row(row, publication):
    row['financing_code'] = financing_code(publication['dataset_version_id'], row.pop('active_fact_id'))
    row['review_reason'] = review_reason(row['overdue_principal'], row['collectibility_code'])
    row['date_anomaly'] = bool(row['maturity_date'] and row['realization_date'] and row['maturity_date'] < row['realization_date'])
    if row['date_anomaly']:
        row['maturity_date'] = None
        row['contract_duration_days'] = None
    return row


def get_monitoring(*, marketing_id=None, sector_id=None, scope='review', collectibility=None,
                   condition='all', search='', sort='arrears_desc', page=1, page_size=10,
                   detail_code=None, expected_publication_id=None, connection_factory=get_connection):
    for value in (marketing_id,sector_id):_validate_id(value)
    _validate_id(expected_publication_id)
    if scope not in {'review','all'} or condition not in {'all','arrears','no_arrears'}:
        raise ValueError('Cakupan tidak dikenali.')
    if collectibility not in {None,'L','KL','D','M','UNKNOWN','NPF'} or sort not in ORDERS:
        raise ValueError('Pilihan tidak dikenali.')
    if isinstance(page,bool) or not isinstance(page,int) or page<1 or page>10**9 or page_size not in {5,10,25,50}:
        raise ValueError('Pagination tidak valid.')
    if not isinstance(search,str) or len(search)>64:raise ValueError('Kode pencarian terlalu panjang.')
    match = re.fullmatch(r'PB-([0-9]{6,20})-([0-9]{6,20})', detail_code) if isinstance(detail_code,str) else None
    if detail_code is not None and (not match or detail_code != financing_code(int(match[1]),int(match[2]))):
        raise ValueError('Kode detail tidak valid.')
    if match and (int(match[1])>18446744073709551615 or int(match[2])>18446744073709551615):
        raise ValueError('Kode detail tidak valid.')
    filters = dict(marketing_id=marketing_id,sector_id=sector_id,scope=scope,collectibility=collectibility,
                   condition=condition,search=search.strip().upper(),sort=sort)
    result = dict(publication=None,filters=filters,status='no_publication',context={'marketing':[],'sectors':[]},
                  summary=dict(contracts=0,contracts_with_arrears=0,npf_contracts=0,
                               outstanding_principal=Decimal('0.00'),overdue_principal=Decimal('0.00')),
                  rows=[],page=1,pages=1,page_size=page_size,detail=None,detail_status=None)
    conn=connection_factory()
    try:
        conn.rollback()
        with conn.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            cursor.execute('START TRANSACTION READ ONLY')
            publication=current_active_publication(cursor)
            result['publication']=publication
            if not publication:return result
            if expected_publication_id is not None and expected_publication_id!=publication['publication_id']:
                result['status']='stale_scope'
                return result
            dataset,reference=publication['dataset_version_id'],publication['reference_dataset_version_id']
            result['context']=_dashboard_context(cursor,publication)
            where=['f.dataset_version_id=%s'];params=[dataset]
            if scope=='review':where.append("(f.overdue_principal>0 OR c.collectibility_code IN ('KL','D','M'))")
            for column,value in (('marketing_id',marketing_id),('sector_id',sector_id)):
                if value is not None:where.append('f.'+column+'=%s');params.append(value)
            if collectibility=='NPF':where.append("c.collectibility_code IN ('KL','D','M')")
            elif collectibility is not None:where.append(CATEGORY+'=%s');params.append(collectibility)
            if condition=='arrears':where.append('f.overdue_principal>0')
            elif condition=='no_arrears':where.append('f.overdue_principal=0')
            if filters['search']:
                where.append("LOCATE(%s,CONCAT('PB-',%s,'-',LPAD(CAST(f.active_fact_id AS CHAR),GREATEST(6,CHAR_LENGTH(CAST(f.active_fact_id AS CHAR))),'0')))>0")
                params.extend((filters['search'],f'{dataset:06d}'))
            sql=JOINS+' WHERE '+' AND '.join(where)
            cursor.execute("""SELECT COUNT(*) AS contracts,COALESCE(SUM(f.overdue_principal>0),0) AS contracts_with_arrears,
              COALESCE(SUM(c.collectibility_code IN ('KL','D','M')),0) AS npf_contracts,
              COALESCE(SUM(f.outstanding_principal),0) AS outstanding_principal,
              COALESCE(SUM(f.overdue_principal),0) AS overdue_principal,
              COALESCE(SUM(m.reference_dataset_version_id IS NULL OR s.reference_dataset_version_id IS NULL
              OR m.reference_dataset_version_id<>%s OR s.reference_dataset_version_id<>%s),0) AS invalid_reference """+sql,
                           (reference,reference,*params))
            summary=cursor.fetchone()
            if summary.pop('invalid_reference'):raise KPIDataError('Kamus tidak sesuai publikasi.')
            for name in ('contracts','contracts_with_arrears','npf_contracts'):summary[name]=int(summary[name])
            result['summary']=summary
            result['status']='available' if summary['contracts'] else 'empty_selection'
            result['pages']=max(1,(summary['contracts']+page_size-1)//page_size)
            result['page']=min(page,result['pages'])
            cursor.execute('SELECT '+FIELDS+' '+sql+' ORDER BY '+ORDERS[sort]+' LIMIT %s OFFSET %s',
                           (*params,page_size,(result['page']-1)*page_size))
            result['rows']=[_row(row,publication) for row in cursor.fetchall()]
            if match:
                if int(match[1]) != dataset:result['detail_status']='stale_version'
                else:
                    cursor.execute('SELECT '+FIELDS+' '+JOINS+''' WHERE f.dataset_version_id=%s AND f.active_fact_id=%s
                      AND m.reference_dataset_version_id=%s AND s.reference_dataset_version_id=%s''',
                                   (dataset,int(match[2]),reference,reference))
                    row=cursor.fetchone()
                    result['detail']=_row(row,publication) if row else None
                    result['detail_status']='available' if row else 'not_found'
            return result
    finally:
        try:conn.rollback()
        finally:conn.close()
