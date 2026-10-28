"""Single published historical snapshot, validated dates only; no Excel in UI."""
from collections import Counter
import json
from src.database.connection import get_connection
from src.database.active_kpis import _percentage
from src.etl.historical import VERSION

DURATIONS={'90':'≤ 90 hari','180':'91–180 hari','365':'181–365 hari','gt365':'> 365 hari'}
NOMINALS={'mikro':'< Rp10.000.000','menengah':'Rp10.000.000–Rp50.000.000','tinggi':'> Rp50.000.000'}
DELAYS=('1–7 hari','8–30 hari','31–90 hari','>90 hari')


def duration_group(days):
    return None if days is None else '90' if days<=90 else '180' if days<=180 else '365' if days<=365 else 'gt365'


def nominal_group(value):
    return None if value is None else 'mikro' if value<10000000 else 'menengah' if value<=50000000 else 'tinggi'


def aggregate_historical(rows,*,year=None,duration=None,nominal=None):
    selected=[];unassignable=0;out=0
    for row in rows:
        checks=[]
        if year is not None:checks.append(None if row['realization_date'] is None else row['realization_date'].year==year)
        if duration is not None:checks.append(None if row['contract_duration_days'] is None else duration_group(row['contract_duration_days'])==duration)
        if nominal is not None:checks.append(None if row['original_principal'] is None else nominal_group(row['original_principal'])==nominal)
        if False in checks:out+=1
        elif None in checks:unassignable+=1
        else:selected.append(row)
    eligible=[r for r in selected if r['eligible']]
    late=sum(r['target_late']==1 for r in eligible);n=len(eligible)
    buckets=[0]*4
    for row in eligible:
        d=row['completion_delay_days']
        if row['target_late']==1:buckets[0 if d<=7 else 1 if d<=30 else 2 if d<=90 else 3]+=1
    groups=[]
    for key,label in DURATIONS.items():
        part=[r for r in eligible if duration_group(r['contract_duration_days'])==key];l=sum(r['target_late']==1 for r in part)
        groups.append(dict(key=key,label=label,contracts=len(part),late=l,on_time=len(part)-l,late_percent=_percentage(l,len(part))))
    return dict(status='available' if n else 'no_eligible_dates' if selected else 'empty_selection',
        contracts=n,on_time=n-late,late=late,on_time_percent=_percentage(n-late,n),late_percent=_percentage(late,n),
        delays=[dict(label=k,contracts=v,percent=_percentage(v,late)) for k,v in zip(DELAYS,buckets)],duration_groups=groups,
        quality=dict(source_rows=len(rows),in_scope=len(selected),excluded_dates=len(selected)-n,excluded_filters=out,
                     unassignable_filters=unassignable,invalid_nominal=sum(r['original_principal'] is None for r in selected),
                     reasons=dict(Counter(issue for r in selected for issue in json.loads(r['date_issues']) if not r['eligible']))),
        years=sorted({r['realization_date'].year for r in rows if r['realization_date']},reverse=True))


def get_historical_summary(*,year=None,duration=None,nominal=None,connection_factory=get_connection):
    if year is not None and (isinstance(year,bool) or not isinstance(year,int) or not 1000<=year<=9999):raise ValueError('Tahun tidak valid.')
    if duration is not None and duration not in DURATIONS:raise ValueError('Durasi tidak valid.')
    if nominal is not None and nominal not in NOMINALS:raise ValueError('Nominal tidak valid.')
    connection=connection_factory()
    try:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ');cursor.execute('START TRANSACTION READ ONLY')
            cursor.execute('''SELECT p.publication_id,p.dataset_version_id,p.published_at,d.dataset_kind,d.status,d.validation_rule_version
                FROM current_publications cp LEFT JOIN dataset_publications p USING(publication_id)
                LEFT JOIN dataset_versions d USING(dataset_version_id) WHERE cp.dataset_kind=%s''',('historical',))
            publication=cursor.fetchone()
            if not publication:return dict(publication=None,status='no_publication',filters=dict(year=year,duration=duration,nominal=nominal))
            if publication['dataset_kind']!='historical' or publication['status']!='published' or publication['validation_rule_version']!=VERSION:raise ValueError('Pointer historis tidak konsisten.')
            cursor.execute('''SELECT realization_date,original_principal,contract_duration_days,eligible,target_late,
                completion_delay_days,date_issues FROM fact_pembiayaan_historis WHERE dataset_version_id=%s''',(publication['dataset_version_id'],))
            result=aggregate_historical(list(cursor.fetchall()),year=year,duration=duration,nominal=nominal)
            return dict(result,publication=publication,filters=dict(year=year,duration=duration,nominal=nominal))
    finally:
        try:connection.rollback()
        finally:connection.close()
