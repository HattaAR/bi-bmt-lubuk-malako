"""Historical SQLRESULT extraction/validation. Never joins active contracts."""
from collections import Counter
from dataclasses import dataclass,field
from decimal import Decimal
import hashlib
from pathlib import Path
from src.etl.active_candidate import Source,fingerprint
from src.etl.validate_active import read_xls,date_value,money_value

VERSION='historical-v1'
DEFAULT_FILE=Path(__file__).resolve().parents[2]/'data/raw/historis/SQLRESULT.XLS'
DATE_FIELDS=('tgl_realisasi','tgl_jatuh_tempo','tgl_akhir_trans')


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
        return dict(rows=len(self.rows),eligible=sum(r['eligible'] for r in self.rows),
                    late=sum(r['target_late']==1 for r in self.rows),
                    original_principal=sum((r['original_principal'] or Decimal(0) for r in self.rows),Decimal(0)),
                    invalid_nominal=sum(r['original_principal'] is None for r in self.rows))

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
        try:principal=money_value(record['jml_pinjaman'])
        except (ValueError,ArithmeticError):principal=None
        row=classify_dates(*dates)
        row.update(source_row_number=line,original_principal=principal,
                   raw_values={k:{'value':record[k].value,'cell_type':record[k].ctype} for k in (*DATE_FIELDS,'jml_pinjaman')})
        rows.append(row)
    candidate=HistoricalCandidate(source,rows);candidate.verify_source();return candidate
