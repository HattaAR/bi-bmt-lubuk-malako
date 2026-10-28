"""Admin-only operations; fresh guards and identity derived from session, never UI."""
from src.auth.session import require_role
from src.database.connection import get_connection
from src.services.admin_upload import (prepare_upload,normalize_metadata,sync_inputs,input_key)
from src.etl.active_candidate import CandidateValidationError,Finding


def validate_upload(state,name,contents,values,**options):
    require_role(state,'admin')
    # Input fingerprint includes even invalid metadata so old results cannot survive.
    flow=sync_inputs(state,input_key(name,contents,{k:str(v) if v is not None else None for k,v in values.items()}))
    flow.clear();flow.update(input_key=input_key(name,contents,{k:str(v) if v is not None else None for k,v in values.items()}),stage=2)
    try:
        metadata=normalize_metadata(values)
        candidate=prepare_upload(name,contents,metadata,**options)
    except CandidateValidationError as error:
        flow.update(valid=False,findings=list(error.findings) or [Finding('INPUT_INVALID','blocking',None,None,None,'Struktur/nilai sumber tidak valid.','etl_active')])
    except (ValueError,OSError):
        flow.update(valid=False,findings=[Finding('INPUT_INVALID','blocking',None,None,None,
            'Berkas, sheet, metadata, atau kamus tidak dapat divalidasi. Periksa format, kolom wajib dan isian laporan.','etl_active')])
    else:
        flow.update(valid=True,candidate=candidate,findings=candidate.findings)
    require_role(state,'admin')
    return flow


def _validated(state):
    flow=state.get('admin_workflow',{})
    if not flow.get('valid') or 'candidate' not in flow:raise ValueError('Lakukan pemeriksaan valid sebelum melanjutkan.')
    flow['candidate'].verify_sources()
    return flow


def load_upload(state,*,warnings_acknowledged=False,connection_factory=None):
    principal=require_role(state,'admin');flow=_validated(state)
    if any(f.severity=='warning' for f in flow['findings']) and not warnings_acknowledged:
        raise ValueError('Tinjau dan akui batas penggunaan warning sebelum memuat kandidat.')
    from src.database.active_candidates import load_candidate
    result=load_candidate(flow['candidate'],admin_user_id=principal.user_id,
                          connection_factory=connection_factory or get_connection)
    require_role(state,'admin')
    flow['loaded']=result
    return result


def preview_upload(state,*,connection_factory=None):
    principal=require_role(state,'admin');flow=_validated(state)
    if 'loaded' not in flow:raise ValueError('Muat kandidat secara eksplisit dahulu.')
    from src.database.publications import preview_active_candidate
    result=preview_active_candidate(flow['loaded'].dataset_version_id,published_by=principal.user_id,
                                    connection_factory=connection_factory or get_connection)
    require_role(state,'admin')
    flow['preview']=result;flow['stage']=3
    state['admin_publish_ack']=False
    return result


def publish_upload(state,*,confirmed=False,connection_factory=None):
    principal=require_role(state,'admin');flow=_validated(state)
    preview=flow.get('preview')
    if not confirmed or not preview or not preview['can_publish']:
        raise ValueError('Preview yang lolos dan konfirmasi admin wajib sebelum publikasi.')
    if preview.get('published_by')!=principal.user_id:raise ValueError('Preview harus dibuat oleh admin sesi ini.')
    from src.database.publications import publish_active_candidate
    previous=preview['previous_publication']
    result=publish_active_candidate(flow['loaded'].dataset_version_id,principal.user_id,
        connection_factory=connection_factory or get_connection,
        expected_current_publication_id=previous['publication_id'] if previous else None)
    require_role(state,'admin')
    flow['published']=result
    return result


def read_admin_history(state,*,connection_factory=None,**filters):
    require_role(state,'admin')
    from src.database.upload_history import get_upload_history
    result=get_upload_history(connection_factory=connection_factory or get_connection,**filters)
    require_role(state,'admin')
    return result


def read_admin_history_detail(state,dataset_id,*,connection_factory=None):
    require_role(state,'admin')
    from src.database.upload_history import get_upload_detail
    result=get_upload_detail(dataset_id,connection_factory=connection_factory or get_connection)
    require_role(state,'admin')
    return result
