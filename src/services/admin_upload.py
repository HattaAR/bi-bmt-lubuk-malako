"""Upload inputs and session-local workflow, reusing ETL/business services."""
from datetime import date
from dataclasses import replace
import hashlib
import os
from pathlib import Path,PureWindowsPath
import re

from src.etl.active_candidate import prepare_candidate,CandidateValidationError,fingerprint,Finding
from src.etl.excel_reader import MAX_UPLOAD_BYTES,check_container,open_book
from src.etl.validate_active import REFERENCE_FILE

ROOT=Path(__file__).resolve().parents[2]


def safe_filename(name):
    if not isinstance(name,str) or any(ord(c)<32 for c in name):raise ValueError('Nama berkas tidak valid.')
    name=PureWindowsPath(name.replace('/','\\')).name
    if (not name or len(name)>160 or re.search(r'[<>:"|?*]',name)
        or Path(name).suffix.lower() not in ('.xls','.xlsx')
        or name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}):
        raise ValueError('Nama berkas harus berupa nama Excel yang valid.')
    return name


def check_upload(name,contents):
    name=safe_filename(name);check_container(name,contents)
    # Structural validation and formula rejection occur before retaining bytes.
    try:
        book=open_book(Path(name),contents)
        try:
            sheets=book.sheet_names()
            if not sheets:raise ValueError('Workbook tidak memiliki sheet.')
            if 'SQLRESULT' not in sheets:raise ValueError('Sheet SQLRESULT wajib tersedia untuk pembiayaan aktif.')
            book.sheet_by_name('SQLRESULT')
        finally:
            if hasattr(book,'release_resources'):book.release_resources()
    except Exception:
        # Workbook parser errors may contain arbitrary source strings/paths.
        raise ValueError('Workbook/sheet tidak valid atau memuat formula yang tidak didukung.') from None
    return name


def _text(value,label,limit):
    if not isinstance(value,str) or not value.strip() or len(value.strip())>limit or any(ord(c)<32 and c not in '\n\t' for c in value):
        raise ValueError(f'{label} wajib diisi dan maksimal {limit} karakter.')
    return value.strip()


def normalize_metadata(values):
    name=_text(values.get('report_name'),'Nama laporan',255)
    scope=_text(values.get('scope_description'),'Cakupan laporan',2000)
    unknown=values.get('position_unknown',True)
    position=None if unknown else values.get('position_date')
    if not unknown and (type(position) is not date or position.year<1000):raise ValueError('Pilih tanggal posisi yang telah dikonfirmasi.')
    export=None;period=None
    if not values.get('export_unknown',True):
        export=values.get('export_date');month=values.get('export_month');year=values.get('export_year')
        if export is not None and (type(export) is not date or export.year<1000):raise ValueError('Tanggal ekspor di luar rentang DATE yang didukung.')
        if (month is None)!=(year is None):raise ValueError('Bulan dan tahun ekspor harus diisi bersama.')
        if month is not None:
            if type(month) is not int or type(year) is not int or not 1<=month<=12 or not 1000<=year<=9999:raise ValueError('Periode ekspor tidak valid.')
            if export and (export.year,export.month)!=(year,month):raise ValueError('Tanggal ekspor berbeda dari bulan/tahun yang dipilih.')
            period=f'{year:04d}-{month:02d}'
        if not export and not period:raise ValueError('Isi periode/tanggal ekspor atau pilih belum diketahui.')
    return dict(report_name=name,scope_description=scope,position_date=position.isoformat() if position else None,
                position_date_status='unknown' if unknown else 'confirmed',
                export_date=export.isoformat() if export else None,export_period_text=period)


def attach_metadata(candidate,metadata):
    """Canonical validated metadata participates in active identity; dictionary stays reusable."""
    # Revalidate persisted JSON, not just browser input.
    month=year=None
    if metadata.get('export_period_text'):
        year,month=map(int,metadata['export_period_text'].split('-'))
    checked=normalize_metadata(dict(report_name=metadata.get('report_name'),scope_description=metadata.get('scope_description'),
        position_unknown=metadata.get('position_date_status')=='unknown',
        position_date=date.fromisoformat(metadata['position_date']) if metadata.get('position_date') else None,
        export_unknown=not (metadata.get('export_date') or metadata.get('export_period_text')),
        export_date=date.fromisoformat(metadata['export_date']) if metadata.get('export_date') else None,
        export_month=month,export_year=year))
    if checked!=metadata:raise ValueError('Metadata laporan tidak konsisten.')
    if candidate.report_metadata:
        if candidate.report_metadata!=metadata:raise ValueError('Metadata kandidat telah ditetapkan; validasi ulang sumber.')
        return candidate
    findings=[f for f in candidate.findings if not (f.rule_code=='POSITION_DATE_UNKNOWN' and metadata['position_date'])]
    return replace(candidate,ingestion_key=fingerprint({'source_identity':candidate.ingestion_key,'report_metadata':metadata}),
                   report_metadata=metadata,position_date=date.fromisoformat(metadata['position_date']) if metadata['position_date'] else None,findings=findings)


def input_key(name,contents,values):
    return fingerprint(dict(filename=name,sha256=hashlib.sha256(contents).hexdigest(),metadata=values))


def sync_inputs(state,key):
    flow=state.get('admin_workflow')
    if not flow or flow.get('input_key')!=key:
        state['admin_workflow']=dict(input_key=key,stage=1)
        state['admin_warning_ack']=False;state['admin_publish_ack']=False
    return state['admin_workflow']


def stage_file(name,contents,*,storage_root=None):
    name=safe_filename(name);root=Path(storage_root or os.getenv('BI_BMT_UPLOAD_DIR',ROOT/'data/uploads')).resolve()
    target=root/hashlib.sha256(contents).hexdigest()/name
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.resolve().is_relative_to(root):raise ValueError('Lokasi unggah tidak valid.')
    try:
        with target.open('xb') as stream:stream.write(contents)
    except FileExistsError:
        if target.read_bytes()!=contents:raise ValueError('Berkas tersimpan tidak cocok dengan hash.')
    return target


def prepare_upload(name,contents,metadata,*,reference_path=None,storage_root=None):
    name=check_upload(name,contents)
    active=stage_file(name,contents,storage_root=storage_root)
    # Snapshot trusted configured dictionary; never join its contract rows.
    ref_path=Path(reference_path or os.getenv('BI_BMT_REFERENCE_FILE',REFERENCE_FILE))
    ref=stage_file(ref_path.name,ref_path.read_bytes(),storage_root=storage_root)
    return attach_metadata(prepare_candidate(active,ref),metadata)
