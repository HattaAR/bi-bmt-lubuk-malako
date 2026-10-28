"""Descriptive concentration from one published snapshot; shared KPI definitions."""
from collections import defaultdict
from decimal import Decimal,localcontext
from src.database.active_kpis import (_aggregate_groups,_dashboard_context,_summarize,_validate_id,
                                      _percentage,MONEY_FIELDS)
from src.database.active_portfolio import current_active_publication
from src.database.connection import get_connection


def _rollup(rows):
    by_code={}
    with localcontext() as context:
        context.prec=50
        for row in rows:
            code=row['category']
            target=by_code.setdefault(code,dict(category=code,contracts=0,contracts_with_arrears=0,
                                               **{key:Decimal('0.00') for key in MONEY_FIELDS}))
            for key in (*MONEY_FIELDS,'contracts','contracts_with_arrears'):target[key]+=row[key]
    return list(by_code.values())


def get_concentration(*, marketing_id=None, sector_id=None, group_by='sector',metric='outstanding',
                      connection_factory=get_connection):
    for value in (marketing_id,sector_id):_validate_id(value)
    if group_by not in {'sector','marketing'} or metric not in {'outstanding','contracts'}:
        raise ValueError('Pengelompokan atau ukuran tidak tersedia.')
    filters=dict(marketing_id=marketing_id,sector_id=sector_id)
    connection=connection_factory()
    try:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            cursor.execute('START TRANSACTION READ ONLY')
            publication=current_active_publication(cursor)
            rows=_aggregate_groups(cursor,publication,filters,dimension=group_by) if publication else []
            totals=_summarize(publication,filters,_rollup(rows))
            result=dict(publication=publication,filters=filters,group_by=group_by,metric=metric,
                        totals=totals['kpis'],status=totals['status'],npf_reason=totals['npf_reason'],
                        unknown_collectibility_contracts=totals['unknown_collectibility_contracts'],
                        context=_dashboard_context(cursor,publication),groups=[],largest=[],
                        metric_available=False,metric_reason='no_publication' if not publication else 'empty_selection')
            grouped=defaultdict(list)
            for row in rows:grouped[row['group_id']].append(row)
            for identifier,items in grouped.items():
                summary=_summarize(publication,filters,items)
                result['groups'].append(dict(id=identifier,label=items[0]['group_label'],
                    mapping_status=items[0]['dimension_status'],kpis=summary['kpis'],
                    npf_reason=summary['npf_reason'],unknown_collectibility_contracts=summary['unknown_collectibility_contracts'],
                    outstanding_share_percent=_percentage(summary['kpis']['outstanding_principal'],result['totals']['outstanding_principal']),
                    contract_share_percent=_percentage(summary['kpis']['active_contracts'],result['totals']['active_contracts'])))
            key='outstanding_principal' if metric=='outstanding' else 'active_contracts'
            share='outstanding_share_percent' if metric=='outstanding' else 'contract_share_percent'
            result['groups'].sort(key=lambda group:(-group['kpis'][key],group['id']))
            for group in result['groups']:group['share_percent']=group[share]
            if result['groups']:
                negative=any(group['kpis'][key]<0 for group in result['groups'])
                result['metric_available']=result['totals'][key]>0 and not negative
                result['metric_reason']='negative_weights' if negative else ('zero_denominator' if result['totals'][key]==0 else None)
                if result['metric_available']:
                    maximum=result['groups'][0]['kpis'][key]
                    result['largest']=[g['id'] for g in result['groups'] if g['kpis'][key]==maximum]
            return result
    finally:
        try:connection.rollback()
        finally:connection.close()
