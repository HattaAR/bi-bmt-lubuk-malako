"""Native monitoring controls and scoped table/detail from referensi desain UI."""
from html import escape
import streamlit as st
from src.ui.shared.paths import ROOT
from src.ui.executive.layout import FILTER_KEYS, CATEGORIES, dimension_filter, reset_filters
from src.ui.shared.formatters import number, rupiah
from src.auth.ui import page_guard

SCOPES={'Perlu Ditinjau':'review','Semua Pembiayaan':'all'}
SORTS={'arrears_desc':'Tunggakan pokok terbesar','outstanding_desc':'Outstanding terbesar','maturity_asc':'Tanggal jatuh tempo paling awal','maturity_desc':'Tanggal jatuh tempo paling akhir'}
CONDITIONS={'all':'Semua','arrears':'Memiliki tunggakan pokok','no_arrears':'Tanpa tunggakan pokok'}
DEFAULTS=dict(monitor_scope='Perlu Ditinjau',monitor_search='',monitor_category=None,
              monitor_condition='all',monitor_sort='arrears_desc',monitor_page=1,
              monitor_page_size=10,monitor_detail=None,monitor_expected_publication=None)
_TABLE=st.components.v2.component('monitor_table',html='<div class="pm-table-mount"></div>',
                                js=(ROOT/'assets/js/monitor_table.js').read_text(encoding='utf-8'),isolate_styles=False)


def initialize():
    for key,value in DEFAULTS.items():st.session_state.setdefault(key,value)


def reset_page():
    st.session_state['monitor_page']=1
    st.session_state['monitor_detail']=None


def reset_monitor():
    reset_filters()
    for key,value in DEFAULTS.items():st.session_state[key]=value


def open_group_monitoring(raw, scope):
    """Navigate only to a group from the rendered, version-bound snapshot."""
    page_guard('executive')
    identifier=int(raw) if isinstance(raw,str) and raw.isascii() and raw.isdecimal() and len(raw)<=20 else None
    if (identifier is None or str(identifier)!=raw or identifier not in scope.get('ids',[])
            or scope.get('group_by') not in {'marketing','sector'}):
        return False
    marketing,sector=scope['marketing_id'],scope['sector_id']
    if scope['group_by']=='sector':sector=identifier
    else:marketing=identifier
    reset_monitor()
    st.session_state[FILTER_KEYS[0]]=marketing
    st.session_state[FILTER_KEYS[1]]=sector
    st.session_state['monitor_scope']='Semua Pembiayaan'
    st.session_state['monitor_expected_publication']=scope['publication_id']
    st.switch_page(ROOT/'pages/executive/monitoring.py')
    return True


def request_args():
    return dict(marketing_id=st.session_state.get(FILTER_KEYS[0]),sector_id=st.session_state.get(FILTER_KEYS[1]),
                scope=SCOPES[st.session_state['monitor_scope']],search=st.session_state['monitor_search'],
                collectibility=st.session_state['monitor_category'],condition=st.session_state['monitor_condition'],
                sort=st.session_state['monitor_sort'],page=st.session_state['monitor_page'],
                page_size=st.session_state['monitor_page_size'],detail_code=st.session_state['monitor_detail'],
                expected_publication_id=st.session_state['monitor_expected_publication'])


def controls(context):
    with st.container(key='monitor_tabs'):
        left,right=st.columns([3,1],vertical_alignment='center')
        with left:st.segmented_control('Cakupan daftar',list(SCOPES),key='monitor_scope',selection_mode='single',required=True,label_visibility='collapsed',on_change=reset_page)
        with right:
            with st.popover('Dasar daftar',icon=':material/info:',width='content'):
                st.write('Perlu Ditinjau: tunggakan pokok positif ATAU kolektibilitas KL/D/M. Setiap kontrak dihitung sekali. Urutan pemeriksaan mengikuti kondisi tercatat, bukan prediksi.')
                st.caption('Kontrak menunggak dan KL/D/M dapat tumpang tindih; jangan menjumlahkan kedua hitungan sebagai kontrak unik.')
    with st.container(key='monitor_filters',border=True):
        first=st.columns([1.2,1,1,0.55],vertical_alignment='center')
        with first[0]:st.text_input('Cari kode pembiayaan',key='monitor_search',placeholder='Cari kode pembiayaan…',max_chars=64,icon=':material/search:',label_visibility='collapsed',on_change=reset_page)
        with first[1]:dimension_filter('Marketing',context['marketing'],FILTER_KEYS[0],on_change=reset_page)
        with first[2]:dimension_filter('Sektor',context['sectors'],FILTER_KEYS[1],on_change=reset_page)
        with first[3]:st.button('Reset filter',on_click=reset_monitor,icon=':material/restart_alt:',width='content')
        second=st.columns([1,1,1.5],vertical_alignment='center')
        labels={None:'Semua Kolektibilitas','NPF':'Kolektibilitas KL/D/M',**{k:v[0] for k,v in CATEGORIES.items()}}
        with second[0]:st.selectbox('Kolektibilitas',list(labels),format_func=labels.get,key='monitor_category',placeholder='Semua Kolektibilitas',on_change=reset_page)
        with second[1]:st.selectbox('Tunggakan Pokok',list(CONDITIONS),format_func=CONDITIONS.get,key='monitor_condition',on_change=reset_page)


def badge(code):
    label=CATEGORIES.get(code,CATEGORIES['UNKNOWN'])[0]
    safe_code=code.lower() if code in CATEGORIES else 'unknown'
    return f'<span class="bmt-category bmt-category-{safe_code}">{label}</span>'


def date(value):
    return value.strftime('%d-%m-%Y') if value else '—'


def table_html(result):
    rows=[]
    for row in result['rows']:
        code=escape(row['financing_code'])
        values=(f'<code>{code}</code>',escape(row['marketing_name'] or 'Tidak diketahui'),badge(row['collectibility_code']),
                rupiah(row['outstanding_principal']),'<strong class="pm-overdue">'+rupiah(row['overdue_principal'])+'</strong>',
                date(row['maturity_date']),escape(row['review_reason']),f'<button type="button" data-detail="{code}" aria-label="Lihat Detail {code}">Lihat Detail →</button>')
        rows.append('<tr>'+''.join('<td>'+value+'</td>' for value in values)+'</tr>')
    if not rows:rows=['<tr><td colspan="8">Tidak ada pembiayaan dalam cakupan filter ini.</td></tr>']
    headings=('Kode Pembiayaan','Marketing','Kolektibilitas','Outstanding','Tunggakan Pokok','Jatuh Tempo','Alasan Ditinjau','Aksi')
    return '<div class="pm-table-scroll" tabindex="0" role="region" aria-label="Daftar pembiayaan"><table class="pm-table"><thead><tr>'+''.join('<th scope="col">'+x+'</th>' for x in headings)+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'


def _open_detail():
    st.session_state['monitor_detail']=st.session_state['monitor_table'].open


def page_move(step):
    st.session_state['monitor_page']+=step


def close_detail():
    st.session_state['monitor_detail']=None


def render_list(result):
    total=result['summary']
    st.session_state['monitor_page']=result['page']
    with st.container(key='monitor_list',border=True):
        with st.container(key='monitor_list_header'):
            heading,sort,model=st.columns([2,1.4,1],vertical_alignment='center')
            with heading:
                st.subheader('Daftar Pembiayaan')
                st.caption(f'{number(total["contracts"])} kontrak · Outstanding {rupiah(total["outstanding_principal"])} · Tunggakan {rupiah(total["overdue_principal"])}')
            with sort:st.selectbox('Urutkan',list(SORTS),format_func=SORTS.get,key='monitor_sort',on_change=reset_page)
            with model:st.checkbox('Skor model belum tersedia',disabled=True)
        _TABLE(data={'html':table_html(result)},key='monitor_table',on_open_change=_open_detail)
        st.html('<div class="pm-table-footer"><span>Kode merupakan ID anonim terikat versi data; bukan nomor rekening.</span><span>'+str(len(result['rows']))+' dari '+number(total['contracts'])+' kontrak</span></div>')
        left,previous,middle,next_col,size=st.columns([1.8,1.4,1,1.2,1.2],vertical_alignment='center')
        with left:st.caption(f'Menunggak: {number(total["contracts_with_arrears"])} · KL/D/M: {number(total["npf_contracts"])}. Hitungan dapat tumpang tindih.')
        with previous:st.button('Sebelumnya',disabled=result['page']==1,on_click=page_move,args=(-1,))
        with middle:st.caption(f'Halaman {result["page"]} / {result["pages"]}')
        with next_col:st.button('Berikutnya',disabled=result['page']==result['pages'],on_click=page_move,args=(1,))
        with size:st.selectbox('Baris per halaman',[5,10,25,50],key='monitor_page_size',label_visibility='collapsed',on_change=reset_page)
    st.html('<div class="pm-note">ⓘ Daftar membantu pemeriksaan berdasarkan kondisi tercatat. Skor model, penugasan, dan riwayat tindak lanjut belum tersedia.</div>')


@st.dialog('Detail Pembiayaan',width='large',on_dismiss=close_detail)
def detail_dialog(result):
    page_guard('executive')
    row=result['detail']
    if row is None:
        st.info('Versi publikasi telah berubah atau pembiayaan tidak ditemukan. Kembali ke daftar untuk memilih ulang.')
    else:
        st.html('<div class="pm-detail-heading"><code>'+escape(row['financing_code'])+'</code>'+badge(row['collectibility_code'])+'</div>')
        summary=(('Outstanding',rupiah(row['outstanding_principal'])),('Tunggakan Pokok',rupiah(row['overdue_principal'])),('Marketing',row['marketing_name'] or 'Tidak diketahui'))
        cards=''.join('<div><span>'+label+'</span><strong>'+escape(value)+'</strong></div>' for label,value in summary)
        st.html('<section class="pm-detail-summary">'+cards+'<p>Alasan ditampilkan: '+escape(row['review_reason'])+'</p></section>')
        information=(('Kode internal',row['financing_code']),('Marketing',row['marketing_name']),('Sektor',row['sector_name']),
                     ('Jenis pembiayaan (kode sumber)',row['financing_type_code']),('Akad (kode sumber)',row['contract_type_code']),
                     ('Nominal pembiayaan awal',rupiah(row['original_principal'])),('Tanggal realisasi',date(row['realization_date'])),
                     ('Tenor sesuai sumber',number(row['recorded_tenor'],2)),('Satuan periode (kode sumber)',row['installment_unit_code']),
                     ('Jatuh tempo kontrak',date(row['maturity_date'])))
        position=(('Outstanding pokok',rupiah(row['outstanding_principal'])),('Tunggakan pokok',rupiah(row['overdue_principal'])),
                  ('Sisa margin',rupiah(row['remaining_margin'])),('Tunggakan denda',None),('Kolektibilitas',CATEGORIES[row['collectibility_code']][0]))
        blocks=[]
        for title,values in (('Informasi Kontrak',information),('Posisi pada Data Sumber',position)):
            blocks.append('<section class="pm-detail-panel"><h3>'+title+'</h3><dl>'+''.join('<div><dt>'+label+'</dt><dd>'+escape(str(value) if value is not None else '—')+'</dd></div>' for label,value in values)+'</dl></section>')
        st.html('<div class="pm-detail-grid">'+''.join(blocks)+'</div>')
        st.caption('Tunggakan pokok merupakan bagian outstanding, bukan nilai tambahan. Tanggal posisi belum dikonfirmasi; indikator waktu tidak dihitung.' if result['publication']['position_date'] is None else 'Tunggakan pokok merupakan bagian outstanding, bukan nilai tambahan.')
        with st.expander('Skor model & konteks sumber'):
            st.write('Skor model, penugasan, dan riwayat tindak lanjut belum tersedia. Simulasi pokok tersedia terpisah tanpa mengubah kontrak.')
            st.caption(f'Publikasi {result["publication"]["publication_id"]} · Dataset {result["publication"]["dataset_version_id"]} · Sheet {row["source_sheet"]} · Baris sumber {row["source_row_number"]}')
        from src.ui.executive.simulation import open_from_monitoring
        st.button('Simulasikan Pokok',on_click=open_from_monitoring,args=(result,),icon=':material/calendar_month:')
    if st.button('Kembali ke daftar',on_click=close_detail):st.rerun()
