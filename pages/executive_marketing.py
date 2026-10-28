from src.ui.assets import asset_text
import streamlit as st
from src.auth.ui import page_guard,protected_action
from src.auth.actions import read_marketing_portfolio
from src.ui.executive import ROOT,FILTER_KEYS,load_styles,header,dimension_filter
from src.ui.marketing import initialize,reset_marketing,render_marketing

principal=page_guard('executive')
initialize()
with st.container(key='executive_home'),st.container(key='executive_marketing_page'):
    st.html('<style>'+asset_text(ROOT/'assets/css/marketing.css')+'</style>')
    result=protected_action(read_marketing_portfolio,marketing_id=st.session_state.get(FILTER_KEYS[0]),sector_id=st.session_state.get(FILTER_KEYS[1]))
    header(principal,result,title='Portofolio Marketing',description='Tinjau kualitas pembiayaan dan kebutuhan pemantauan pada setiap portofolio marketing.')
    if result['publication'] is None:
        st.info('Belum ada publikasi aktif. Portofolio marketing tersedia setelah data diterbitkan administrator.')
    else:
        with st.container(key='executive_filters',border=True):
            marketing,sector,reset=st.columns([1,1,1],vertical_alignment='center')
            with marketing:dimension_filter('Marketing',result['context']['marketing'],FILTER_KEYS[0])
            with sector:dimension_filter('Sektor',result['context']['sectors'],FILTER_KEYS[1])
            with reset:st.button('Reset filter',on_click=reset_marketing,icon=':material/restart_alt:')
        if result['unknown_collectibility_contracts']:st.info('NPF belum lengkap: terdapat kategori kolektibilitas tidak dikenali. Nominal tetap disajikan.')
        if st.session_state.pop('_marketing_message',False):st.warning('Marketing tidak lagi tersedia. Pilih ulang dari tampilan terbaru.')
        render_marketing(result)
