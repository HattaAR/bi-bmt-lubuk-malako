import streamlit as st
from src.auth.actions import read_executive_kpis
from src.auth.ui import page_guard,protected_action
from src.ui.executive.layout import FILTER_KEYS,filters
from src.ui.executive.home import (load_home_styles,home_header,composition_chart,
                                   category_panel,review_table,summary_cards)

principal=page_guard('executive')
load_home_styles()
with st.container(key='executive_home'),st.container(key='home_redesign',gap=None):
    result=protected_action(read_executive_kpis,marketing_id=st.session_state.get(FILTER_KEYS[0]),sector_id=st.session_state.get(FILTER_KEYS[1]),include_context=True)
    home_header(principal,result)
    if result['publication'] is None:
        st.info('Belum ada publikasi aktif. Ringkasan tersedia setelah data diterbitkan administrator.')
    else:
        filters(result['context'])
        if result['status']=='empty_selection':st.info('Tidak ada kontrak pada kombinasi filter ini. Ubah pilihan atau reset filter.')
        reasons={'zero_outstanding':'NPF tidak tersedia karena total outstanding nol.','unknown_collectibility':'NPF belum lengkap karena terdapat kategori kolektibilitas tidak dikenali.','empty_selection':'NPF tidak tersedia karena hasil filter kosong.'}
        if result['npf_reason'] in reasons:st.info(reasons[result['npf_reason']])
        with st.container(key='home_visuals',gap=None):
            main,support=st.columns([2.05,1],gap='medium')
            with main,st.container(key='executive_composition',border=True):
                with st.container(key='home_chart_header',horizontal=True,vertical_alignment='center'):
                    st.subheader('Komposisi Kolektibilitas',anchor='komposisi')
                    basis=st.segmented_control('Ukuran komposisi',['Jumlah Kontrak','Outstanding'],default='Outstanding',key='executive_composition_basis',label_visibility='collapsed',selection_mode='single')
                composition_chart(result,basis or 'Outstanding')
            with support:category_panel(result)
        summary_cards(result)
        with st.container(key='executive_review',border=True):
            with st.container(key='executive_review_header'):
                left,right=st.columns([3,1],vertical_alignment='center')
                with left:
                    st.subheader('Pembiayaan untuk Ditinjau',anchor='pembiayaan-ditinjau')
                    st.caption('Urutan pemeriksaan berdasarkan tunggakan pokok terbesar.')
                with right:st.page_link('pages/executive/monitoring.py',label='Semua pemantauan',icon=':material/arrow_forward:')
            review_table(result['context']['review'])
        with st.container(key='home_quality_link'):
            st.page_link('pages/executive/quality.py',label='Lihat Kualitas Portofolio',icon=':material/arrow_forward:')
