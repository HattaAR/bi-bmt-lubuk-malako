from src.ui.assets import asset_text
import streamlit as st
from src.auth.ui import page_guard,protected_action
from src.auth.actions import read_concentration
from src.ui.executive import ROOT,FILTER_KEYS,load_styles,header
from src.ui.concentration import initialize,controls,render_concentration

principal=page_guard('executive')
initialize()
with st.container(key='executive_home'),st.container(key='executive_concentration'):
    st.html('<style>'+asset_text(ROOT/'assets/css/concentration.css')+'</style>')
    result=protected_action(read_concentration,marketing_id=st.session_state.get(FILTER_KEYS[0]),
        sector_id=st.session_state.get(FILTER_KEYS[1]),group_by=st.session_state['concentration_group'],metric=st.session_state['concentration_metric'])
    header(principal,result,title='Konsentrasi Portofolio',description='Kenali kelompok yang menampung pembiayaan terbesar dan tinjau kualitasnya.')
    if result['publication'] is None:
        st.info('Belum ada publikasi aktif. Konsentrasi tersedia setelah data diterbitkan administrator.')
    else:
        controls(result['context'])
        if result['status']=='empty_selection':st.info('Tidak ada kontrak pada cakupan filter ini. Ubah pilihan atau reset filter.')
        elif not result['metric_available']:st.info('Treemap belum tersedia: total ukuran nol atau terdapat bobot negatif. Tabel tetap menampilkan nilai sumber.')
        if result['npf_reason']=='unknown_collectibility':st.info('NPF belum lengkap: terdapat kategori kolektibilitas tidak dikenali.')
        if st.session_state.pop('_concentration_message',None):st.warning('Kelompok tidak lagi tersedia. Pilih ulang dari tampilan terbaru.')
        render_concentration(result)
