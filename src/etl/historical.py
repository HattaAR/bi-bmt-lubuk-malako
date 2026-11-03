"""Historical SQLRESULT extraction/validation. Never joins active contracts."""
from collections import defaultdict
from dataclasses import dataclass,field
from decimal import Decimal
import hashlib
from pathlib import Path
from src.etl.active_candidate import Source,fingerprint
from src.etl.validate_active import read_xls,date_value,money_value

VERSION='historical-v3-bmt-confirmed'
READABLE_VERSIONS={'historical-v1','historical-v2-audit',VERSION}
# Business evidence supplied by the user on behalf of BMT, 3 November 2026.
# Scoped to audited bytes/sheet, never a blanket deduplication override.
IDENTICAL_ROWS_DECISIONS={
    ('ddcf0647dc2cead8a19c2878d2bcea9149ee2fc86d6cc3b288d16c364333df28','SQLRESULT'):
        dict(decision_id='BMT-HIST-2026-11-03-KEEP-ALL',confirmed_on='2026-11-03',
             interpretation='distinct_financings_equal_values',retain_all_records=True,
             evidence='Konfirmasi BMT disampaikan pengguna: nilai identik merupakan pembiayaan berbeda.')
}
DEFAULT_FILE=Path(__file__).resolve().parents[2]/'data/raw/historis/SQLRESULT.XLS'
DATE_FIELDS=('tgl_realisasi','tgl_jatuh_tempo','tgl_akhir_trans')


def identical_rows_decision(source_identity):
    if not source_identity:return None
    decision=IDENTICAL_ROWS_DECISIONS.get((source_identity['sha256'],source_identity['sheet']))
    return dict(decision) if decision else None


def summarize(rows):
    n=len(rows);eligible=sum(bool(r['eligible']) for r in rows)
    late=sum(r['target_late']==1 for r in rows)
    return dict(rows=n,eligible=eligible,late=late,
                original_principal=sum((r['original_principal'] or Decimal(0) for r in rows),Decimal(0)),
                invalid_nominal=sum(r['original_principal'] is None for r in rows))


def comparison_summary(rows):
    result=summarize(rows);n=result['eligible'];late=result['late']
    return dict(result,on_time=n-late,excluded_dates=result['rows']-n,
                on_time_percent=Decimal(n-late)*100/n if n else None,
                late_percent=Decimal(late)*100/n if n else None)


def historical_digest(rows):
    """Canonical parsed facts AND full raw lineage, independent of MySQL types."""
    values=[]
    for row in sorted(rows,key=lambda r:r['source_row_number']):
        item={k:row[k] for k in ('source_row_number','realization_date','original_maturity_date',
            'completion_date','contract_duration_days','target_late','completion_delay_days','date_issues','raw_values')}
        item['eligible']=int(row['eligible'])
        for key in ('realization_date','original_maturity_date','completion_date'):
            item[key]=item[key].isoformat() if item[key] is not None else None
        principal=row['original_principal']
        item['original_principal']=format(principal,'.2f') if principal is not None else None
        values.append(item)
    return fingerprint(values)


def classify_dates(realization,maturity,completion):
    issues=[]
    if any(d is None for d in (realization,maturity,completion)):issues.append('missing_or_invalid_date')
    duration=(maturity-realization).days if realization and maturity and maturity>=realization else None
    if realization and maturity and maturity<realization:issues.append('maturity_before_realization')
    if realization and completion and completion<realization:issues.append('completion_before_realization')
    valid=not issues
    return dict(realization_date=realization,original_maturity_date=maturity,completion_date=completion,
                contract_duration_days=duration,eligible=valid,target_late=int(completion>maturity) if valid else None,
                completion_delay_days=max(0,(completion-maturity).days) if valid else None,date_issues=issues)


@dataclass
class HistoricalCandidate:
    source:Source
    rows:list=field(repr=False)

    @property
    def key(self):return fingerprint({'source':self.source.identity(),'rules':VERSION})

    @property
    def summary(self):
        return summarize(self.rows)

    @property
    def audit(self):
        # All imported columns, cell types and values participate; never dedup
        # by just dates/nominal. Empty raw fixtures cannot prove equality.
        groups=defaultdict(list);distinct=[]
        available=all(bool(r['raw_values']) for r in self.rows)
        for row in self.rows:
            key=fingerprint(row['raw_values']) if available else str(row['source_row_number'])
            if not groups[key]:distinct.append(row)
            groups[key].append(row['source_row_number'])
        duplicates=[g for g in groups.values() if len(g)>1]
        decision=identical_rows_decision(self.source.identity()) if self.source else None
        return dict(grain='source_record_per_dataset_version',unique_contracts=None,
                    exact_row_check_available=available,
                    source_columns=list(self.rows[0]['raw_values']) if self.rows else [],
                    duplicate_groups=duplicates,duplicate_group_count=len(duplicates),
                    duplicate_extra_records=sum(len(g)-1 for g in duplicates),
                    identical_records=sum(len(g) for g in duplicates),
                    all_records=comparison_summary(self.rows),
                    sensitivity_distinct_rows=comparison_summary(distinct) if available else None,
                    identical_rows_decision=decision,
                    publication_decision=('confirmed_distinct_records_keep_all' if decision else
                        'awaiting_bmt_identical_rows' if duplicates else 'no_identical_rows_detected'))

    def verify_source(self):
        if hashlib.sha256(self.source.path.read_bytes()).hexdigest()!=self.source.sha256:raise ValueError('Sumber berubah setelah validasi.')


def prepare_historical(path=DEFAULT_FILE,*,sheet='SQLRESULT'):
    path=Path(path);content=path.read_bytes()
    source=Source(path.resolve(),sheet,hashlib.sha256(content).hexdigest(),len(content))
    book,records=read_xls(path,sheet,{*DATE_FIELDS,'jml_pinjaman'},verbose=False,file_contents=content)
    rows=[]
    for line,record in records:
        dates=[]
        for name in DATE_FIELDS:
            try:dates.append(date_value(record[name],book.datemode))
            except (ValueError,OverflowError,TypeError):dates.append(None)
        try:
            principal=money_value(record['jml_pinjaman'])
            if principal>Decimal('9999999999999999.99'):raise ValueError('Nominal di luar DECIMAL(18,2).')
        except (ValueError,ArithmeticError):principal=None
        row=classify_dates(*dates)
        row.update(source_row_number=line,original_principal=principal,
                   raw_values={k:{'value':cell.value,'cell_type':cell.ctype} for k,cell in record.items()})
        rows.append(row)
    candidate=HistoricalCandidate(source,rows);candidate.verify_source();return candidate
