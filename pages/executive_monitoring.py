from src.ui.assets import asset_text
import streamlit as st
from src.auth.ui import page_guard,protected_action
from src.auth.actions import read_monitoring
from src.ui.executive import load_styles,header,ROOT
from src.ui.monitoring import initialize,request_args,controls,render_list,detail_dialog,reset_monitor

principal=page_guard('executive')
initialize()
with st.container(key='executive_home'),st.container(key='executive_monitoring'):
    st.html('<style>'+asset_text(ROOT/'assets/css/monitoring.css')+'</style>')
    result=protected_action(read_monitoring,**request_args())
    header(principal,result,title='Pemantauan & Prioritas',description='Tinjau kondisi pembiayaan dan tentukan kebutuhan pemeriksaan lebih lanjut.')
    if result['publication'] is None:
        st.info('Belum ada publikasi aktif. Daftar tersedia setelah data diterbitkan administrator.')
    elif result['status']=='stale_scope':
        st.info('Publikasi telah berubah. Pilih ulang kelompok dari Konsentrasi atau reset filter.')
        st.page_link(ROOT/'pages/executive_concentration.py',label='Kembali ke Konsentrasi Portofolio')
        st.button('Reset filter',on_click=reset_monitor)
    else:
        controls(result['context'])
        if result['status']=='empty_selection':st.info('Tidak ada pembiayaan pada cakupan filter ini. Ubah pilihan atau reset filter.')
        render_list(result)
        if st.session_state['monitor_detail'] is not None:detail_dialog(result)
