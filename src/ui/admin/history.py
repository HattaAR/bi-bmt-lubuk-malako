"""Read-only history using the paired referensi desain UI and shared admin shell."""
from datetime import timedelta
from html import escape
import json
import streamlit as st
from src.ui.shared.paths import ROOT
from src.ui.shared.formatters import number
from src.ui.shared.assets import asset_text
from src.ui.admin import layout as admin
from src.auth.admin_actions import read_admin_history, read_admin_history_detail
from src.auth.ui import page_guard

KINDS={None:'Semua Jenis','active':'Pembiayaan aktif','historical':'Historis selesai','transactions':'Transaksi'}
STATUSES={None:'Semua Status','current':'Digunakan dashboard','previous':'Pernah diterbitkan',
          'published':'Seluruh terbitan','ready':'Siap diterbitkan','invalid':'Perlu perbaikan','draft':'Draft','validating':'Dalam pemeriksaan'}
LABELS={'published':'Diterbitkan','ready':'Siap diterbitkan','invalid':'Perlu perbaikan','draft':'Draft','validating':'Dalam pemeriksaan'}
SORTS={'uploaded_desc':'Unggahan terbaru','uploaded_asc':'Unggahan terlama','name_asc':'Nama laporan A–Z'}
DEFAULTS=dict(ah_search='',ah_kind=None,ah_status=None,ah_sort='uploaded_desc',ah_page=1,ah_size=10,ah_selected=None)
_TABLE=st.components.v2.component('upload_history_table',html='<div class="ah-table-mount"></div>',
    js=asset_text(ROOT/'assets/js/history_table.js'),isolate_styles=False)


def text(value,unknown='Belum diketahui'):
    return escape(str(value)) if value is not None and value!='' else unknown


def timestamp(value):
    # Shared connection sets the MySQL session timezone to UTC.
    if value is None:return 'Belum tercatat'
    local=value+timedelta(hours=7)
    month=('Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des')[local.month-1]
    return f'{local.day:02d} {month} {local.year}, {local:%H.%M} WIB'


def position(row):
    if row['position_date'] is None:return '<span class="ah-chip warning">● Belum diketahui</span>'
    return text(row['position_date'].strftime('%d-%m-%Y'))+('' if row['position_date_status']=='confirmed' else '<small>Belum dikonfirmasi</small>')


def changed():
    st.session_state['ah_page']=1
    st.session_state['ah_selected']=None


def reset():
    for key,value in DEFAULTS.items():st.session_state[key]=value


def move(delta):
    st.session_state['ah_page']+=delta
    st.session_state['ah_selected']=None


def close_detail():st.session_state['ah_selected']=None


def open_detail():
    raw=st.session_state.get('ah_table',{}).get('open')
    if isinstance(raw,str) and raw.isascii() and raw.isdecimal() and int(raw) in st.session_state.get('ah_visible_ids',[]):
        st.session_state['ah_selected']=int(raw)


def current_panel(current):
    cards=[]
    for kind,label in [('active','Pembiayaan Aktif'),('historical','Pembiayaan Historis')]:
        row=current[kind]
        cards.append('<div class="ah-source '+('active' if row else '')+'"><div class="ah-source-top"><span>● '+label+'</span><span class="ah-chip '+('active' if row else '')+'">'+('AKTIF' if row else 'BELUM DITERBITKAN')+'</span></div><strong>'+text(row['report_name'] if row else None,'Belum ada sumber terpublikasi')+'</strong><p>'+('Tanggal posisi '+('belum diketahui.' if row['position_date'] is None else text(row['position_date'])+'.') if row else 'Belum digunakan sebagai sumber dashboard.')+'</p></div>')
    st.html('<section class="ah-panel"><div class="ah-section">'+admin.icon('file')+'<div><h2>Sumber Dashboard Saat Ini</h2><p>Versi yang sedang digunakan dashboard; terpisah dari filter riwayat.</p></div></div><div class="ah-current">'+''.join(cards)+'</div></section>')


def filters():
    with st.container(key='ah_filters'):
        columns=st.columns([4.5,2,2.3,1.4],gap='small',vertical_alignment='bottom')
        with columns[0]:st.text_input('Cari nama laporan atau file',key='ah_search',placeholder='Cari nama laporan atau file…',label_visibility='collapsed',icon=':material/search:',max_chars=180,on_change=changed)
        with columns[1]:st.selectbox('Jenis',list(KINDS),format_func=KINDS.get,key='ah_kind',on_change=changed,placeholder='Semua Jenis')
        with columns[2]:st.selectbox('Status',list(STATUSES),format_func=STATUSES.get,key='ah_status',on_change=changed,placeholder='Semua Status')
        with columns[3]:st.button('Reset Filter',key='ah_reset',on_click=reset,icon=':material/restart_alt:',width='stretch')


def table(result):
    st.session_state['ah_visible_ids']=[r['dataset_version_id'] for r in result['rows']]
    rows=[]
    for row in result['rows']:
        state='published' if row['publication_id'] else row['status']
        usage='✓ Digunakan dashboard' if row['is_current'] else 'Pernah diterbitkan' if row['publication_id'] else 'Belum digunakan'
        cells=['<strong>'+text(row['report_name'],'Nama laporan belum tercatat')+'</strong><small class="ah-file">'+text(row['filenames'],'Berkas belum tercatat')+'</small>',
            '<span class="ah-kind '+row['dataset_kind']+'">'+KINDS[row['dataset_kind']]+'</span>',
            '<time>'+text(timestamp(row['uploaded_at']))+'</time><small>'+text(row['uploaders'],'Pengunggah belum tercatat')+'</small>',position(row),
            '<span class="ah-chip '+state+'">'+LABELS.get(state,text(state))+'</span>',
            '<span class="'+('ah-usage' if row['is_current'] else '')+'">'+usage+'</span>',
            '<button type="button" data-detail="'+str(row['dataset_version_id'])+'" aria-label="Lihat detail '+text(row['report_name'] or 'laporan')+'">Lihat Detail →</button>']
        rows.append('<tr>'+''.join('<td>'+cell+'</td>' for cell in cells)+'</tr>')
    html='<div class="ah-scroll"><table class="ah-table"><thead><tr>'+''.join('<th>'+h+'</th>' for h in ['Laporan / File','Jenis Data','Waktu Unggah','Tanggal Posisi','Status Proses','Penggunaan','Aksi'])+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>' if rows else '<div class="ah-empty">Tidak ada riwayat yang sesuai filter.</div>'
    with st.container(key='ah_inventory'):
        _TABLE(data={'html':html},key='ah_table',on_open_change=open_detail)
        with st.container(key='ah_toolbar'):
            summary=result['summary'];a,sort,b,c,d,e=st.columns([3,2.2,1.3,1.2,.8,1.2],gap='small')
            start=(result['page']-1)*result['page_size']+1 if summary['total'] else 0
            with a:st.markdown(f"Menampilkan **{start}–{start+len(rows)-1 if rows else 0} dari {number(summary['total'])}** versi")
            with sort:st.selectbox('Urutkan',list(SORTS),format_func=SORTS.get,key='ah_sort',on_change=changed,label_visibility='collapsed')
            with b:st.selectbox('Baris per halaman',[5,10,25,50],key='ah_size',on_change=changed,label_visibility='collapsed')
            with c:st.button('Sebelumnya',key='ah_prev',on_click=move,args=(-1,),disabled=result['page']==1)
            with d:st.markdown(f"**{result['page']} / {result['pages']}**")
            with e:st.button('Berikutnya',key='ah_next',on_click=move,args=(1,),disabled=result['page']==result['pages'])
            st.caption(f"Seluruh hasil filter: {summary['ready']} siap diterbitkan · {summary['published']} pernah diterbitkan · {summary['current']} sedang digunakan · {summary['invalid']} perlu perbaikan.")


def pairs(entries):
    st.html('<dl>'+''.join('<div><dt>'+text(k)+'</dt><dd>'+text(v)+'</dd></div>' for k,v in entries)+'</dl>')


@st.dialog('Detail Riwayat Unggahan',width='large',on_dismiss=close_detail)
def detail_dialog(identifier):
    page_guard('admin')
    detail=admin.call(read_admin_history_detail,identifier)
    row=detail['version']
    with st.container(key='ah_detail'):
        st.subheader(row['report_name'] or 'Nama laporan belum tercatat')
        scope=row['scope_description']
        try:
            parsed=json.loads(scope)
            scope=parsed.get('report_metadata',{}).get('scope_description') if isinstance(parsed,dict) else None
        except (ValueError,TypeError):pass
        pairs([('Jenis dataset',KINDS[row['dataset_kind']]),('Status kandidat',LABELS.get(row['status'],row['status'])),
               ('Waktu unggah',timestamp(row['uploaded_at'])),('Pengunggah',row['uploaders']),
               ('Tanggal posisi',row['position_date']),('Status tanggal posisi',row['position_date_status']),
               ('Waktu ekspor',row['export_date'] or row['export_period_text']),('Cakupan',scope)])
        st.markdown('### Hasil validasi tersimpan')
        counts=detail['finding_counts']
        st.caption(f"{counts['blocking']} penghambat · {counts['warning']} warning · {counts['information']} informasi. Catatan tersimpan, bukan pemeriksaan ulang Excel.")
        if not detail['findings']:st.info('Tidak ada temuan rinci yang tercatat. Ketiadaan catatan bukan bukti seluruh pemeriksaan lulus.')
        for finding in detail['findings']:
            impact=admin.WARNING_IMPACT.get(finding['rule_code'])
            st.html('<div><strong>'+text(finding['severity'])+' · '+text(finding['rule_code'])+'</strong><small>'+text(finding['field_name'],'Laporan')+' · Baris '+text(finding['source_row_number'],'—')+'</small><p>'+text(finding['message'])+'</p>'+('<small>Dampak: '+text(impact)+'</small>' if impact else '')+'</div>')
        if sum(counts.values())>detail['findings_limit']:st.caption('Maksimal 100 temuan rinci ditampilkan; jumlah di atas mencakup seluruh temuan.')
        st.markdown('### Rekonsiliasi tersimpan')
        if not detail['reconciliation']:st.info('Rekonsiliasi tidak tercatat; tidak dihitung ulang dari sumber.')
        for control in detail['reconciliation']:
            st.caption('Catatan '+timestamp(control['created_at'])+'; bukan rekonsiliasi baru.')
            if control['summary']:st.json(control['summary'],expanded=True)
            else:st.caption('Ringkasan tersimpan tidak dapat dibaca.')
        publication=detail['publication']
        st.markdown('### Publikasi')
        if publication:
            pairs([('Penggunaan','Digunakan dashboard' if publication['is_current'] else 'Pernah diterbitkan; bukan sumber dashboard saat ini'),
                   ('Waktu publikasi',timestamp(publication['published_at'])),('Diterbitkan oleh',publication['published_by']),
                   ('ID publikasi',publication['publication_id']),('Publikasi sebelumnya',publication['previous_publication_id']),('Versi kamus',publication['reference_dataset_version_id'])])
        else:st.info('Versi ini belum pernah diterbitkan.')
        with st.expander('Berkas, fingerprint & versi aturan'):
            pairs([('Versi dataset',identifier),('Dibuat',timestamp(row['created_at'])),('Skema',row['schema_version']),('Pemetaan',row['mapping_version']),('Validasi',row['validation_rule_version'])])
            for source in detail['sources']:
                pairs([('File',source['original_filename']),('Peran sumber',source['source_role']),('Sheet',source['sheet_name']),('Ukuran byte',source['byte_size']),('SHA-256',source['file_sha256']),('Pengunggah',source['uploaded_by'])])
        st.caption('Baca saja. Hapus, rollback, unduh sumber, dan terbitkan ulang tidak tersedia di halaman ini.')
        if st.button('Tutup Detail',key='ah_close'):
            close_detail()
            st.rerun()


def render():
    for key,value in DEFAULTS.items():st.session_state.setdefault(key,value)
    st.html('<style>'+asset_text(ROOT/'assets/css/admin_history.css')+'</style>')
    with st.container(key='admin_page'),st.container(key='admin_history_page'):
        left,right=st.columns([4,1.65],vertical_alignment='top')
        with left:st.html('<header class="adm-header"><div><div class="adm-breadcrumb">Admin / Riwayat Unggahan</div><h1>Riwayat Unggahan</h1><p>Telusuri hasil pemeriksaan, penerbitan, dan sumber data dashboard.</p></div></header>')
        with right,st.container(key='ah_new_upload'):st.page_link(ROOT/'pages/admin/upload.py',label='Unggah Data Baru',icon=':material/add:')
        top=st.container()
        filters()
        result=admin.call(read_admin_history,search=st.session_state['ah_search'],kind=st.session_state['ah_kind'],status=st.session_state['ah_status'],sort=st.session_state['ah_sort'],page=st.session_state['ah_page'],page_size=st.session_state['ah_size'])
        st.session_state['ah_page']=result['page']
        with top:current_panel(result['current'])
        table(result)
        st.html('<aside class="ah-governance"><strong>Tata Kelola Pengunggahan:</strong> Riwayat mencatat versi pembiayaan yang tersimpan. Banyak unggahan bukan banyak periode laporan. Tanggal unggah/publikasi bukan tanggal posisi. Kegagalan yang tidak tersimpan tidak ditampilkan.</aside>')
        st.html('<footer class="ah-footer">Sistem Business Intelligence KSPPS BMT Lubuk Malako • Modul Administrasi &amp; Riwayat Unggahan</footer>')
        if st.session_state['ah_selected'] in st.session_state.get('ah_visible_ids',[]):detail_dialog(st.session_state['ah_selected'])
