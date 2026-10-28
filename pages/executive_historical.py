from src.ui.assets import asset_text
import streamlit as st
from src.auth.ui import page_guard,protected_action
from src.auth.actions import read_historical
from src.database.historical_analysis import DURATIONS,NOMINALS
from src.ui.executive import ROOT,load_styles,number
from src.ui.historical import KEYS,reset_historical,analysis_html

principal=page_guard('executive')
with st.container(key='executive_home'),st.container(key='executive_historical_page'):
    st.html('<style>'+asset_text(ROOT/'assets/css/historical.css')+'</style>')
    result=protected_action(read_historical,year=st.session_state.get(KEYS[0]),duration=st.session_state.get(KEYS[1]),nominal=st.session_state.get(KEYS[2]))
    st.html('<header class="bmt-page-header"><div><h1>Analisis Historis</h1><p>Pola penyelesaian pembiayaan berdasarkan kontrak yang telah selesai.</p></div><span class="bmt-source-badge">Sumber: <strong>SQLRESULT</strong></span></header>')
    if result['publication'] is None:
        st.info('Data historis belum tersedia: belum ada publikasi SQLRESULT. Data aktif tidak digunakan sebagai pengganti.')
    else:
        with st.container(key='historical_filters',border=True):
            columns=st.columns(4,vertical_alignment='bottom')
            with columns[0]:
                if st.session_state.get(KEYS[0]) not in [None,*result['years']]:st.session_state[KEYS[0]]=None;st.rerun()
                st.selectbox('Tahun realisasi',[None,*result['years']],key=KEYS[0],format_func=lambda y:'Semua tahun' if y is None else str(y),help='Tahun realisasi kontrak awal, bukan tahun penyelesaian.')
            with columns[1]:st.selectbox('Durasi kontrak',[None,*DURATIONS],format_func=lambda k:DURATIONS.get(k,'Semua durasi'),key=KEYS[1])
            with columns[2]:st.selectbox('Nominal pembiayaan',[None,*NOMINALS],format_func=lambda k:NOMINALS.get(k,'Semua nominal'),key=KEYS[2])
            with columns[3]:st.button('Reset Filter',on_click=reset_historical,icon=':material/restart_alt:',width='stretch')
        if result['status']!='available':st.info('Tidak ada kontrak dengan tanggal valid pada cakupan filter ini. Nilai persentase tidak tersedia.')
        st.html(analysis_html(result))
        with st.expander('Definisi, cakupan, dan kualitas data'):
            st.write('Selesai = tgl_akhir_trans; jatuh tempo awal = tgl_jatuh_tempo SQLRESULT. Terlambat bila selesai > jatuh tempo; hari terlambat = selisih tanggal tersebut. Realisasi, jatuh tempo, dan selesai wajib valid; jatuh tempo/selesai tidak boleh mendahului realisasi.')
            st.write('Cakupan periode mengikuti tahun realisasi. Grafik distribusi memakai penyebut seluruh kontrak terlambat bertanggal valid dalam filter. KPI memakai seluruh kontrak dianalisis; persentase tabel memakai jumlah kontrak valid pada kelompok durasi masing-masing.')
            st.write('Durasi kontrak = jatuh tempo awal − realisasi dalam hari. Kelompok nominal: < Rp10 juta; Rp10–50 juta (kedua batas masuk); > Rp50 juta. Ini kelompok deskriptif, bukan kategori risiko.')
            q=result['quality']
            st.write(f"Sumber: {number(q['source_rows'])} record; dalam cakupan: {number(q['in_scope'])}; tanggal dikecualikan dari KPI, grafik, dan tabel: {number(q['excluded_dates'])}; di luar filter: {number(q['excluded_filters'])}; tidak dapat ditentukan memenuhi filter: {number(q['unassignable_filters'])}; nominal tidak valid dalam cakupan: {number(q['invalid_nominal'])}.")
            st.write('Nominal tidak valid tetap dapat masuk analisis tanggal tanpa filter nominal; saat filter nominal dipilih, record itu tidak dapat ditempatkan dalam cakupan. Alasan tanggal bisa tumpang tindih pada record yang sama.')
            if q['reasons']:st.json(q['reasons'])
            st.caption(f"Publikasi historis {result['publication']['publication_id']}; versi {result['publication']['dataset_version_id']}. Tidak dihubungkan ke rekening aktif atau transaksi.")
        st.html('<p class="hi-disclaimer">Pola historis pembiayaan selesai tidak memastikan hasil pembiayaan aktif; bukan tren outstanding/NPF atau prediksi.</p>')
