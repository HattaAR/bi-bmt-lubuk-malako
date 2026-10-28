import streamlit as st
from src.auth.actions import read_executive_kpis
from src.auth.ui import page_guard, protected_action
from src.ui.executive import (FILTER_KEYS, composition_chart, filters, header, load_styles, number, review_table, summary_cards)

principal = page_guard('executive')
with st.container(key='executive_home'):
    result = protected_action(read_executive_kpis, marketing_id=st.session_state.get(FILTER_KEYS[0]), sector_id=st.session_state.get(FILTER_KEYS[1]), include_context=True)
    header(principal, result)
    if result['publication'] is None:
        st.info('Belum ada publikasi aktif. Ringkasan tersedia setelah data diterbitkan administrator.')
    else:
        filters(result['context'])
        if result['status'] == 'empty_selection':
            st.info('Tidak ada kontrak pada kombinasi filter ini. Ubah pilihan atau reset filter.')
        summary_cards(result)
        reasons = {'zero_outstanding':'NPF tidak tersedia karena total outstanding nol.', 'unknown_collectibility':'NPF belum lengkap karena terdapat kategori kolektibilitas tidak dikenali.', 'empty_selection':'NPF tidak tersedia karena hasil filter kosong.'}
        if result['npf_reason'] in reasons:
            st.info(reasons[result['npf_reason']])
        with st.container(key='executive_composition', border=True):
            left, right = st.columns([3,2], vertical_alignment='center')
            with left:
                st.subheader('Komposisi Kolektibilitas', anchor='komposisi')
                st.caption('Proporsi portofolio berdasarkan kolektibilitas')
            with right:
                basis = st.segmented_control('Ukuran komposisi', ['Jumlah Kontrak','Outstanding'], default='Outstanding', key='executive_composition_basis', label_visibility='collapsed', selection_mode='single')
            composition_chart(result, basis or 'Outstanding')
            st.page_link('pages/executive_quality.py', label='Lihat Kualitas Portofolio', icon=':material/arrow_forward:')
        with st.container(key='executive_review', border=True):
            with st.container(key='executive_review_header'):
                left,right = st.columns([3,1], vertical_alignment='center')
                with left:
                    st.subheader('Pembiayaan untuk Ditinjau', anchor='pembiayaan-ditinjau')
                    st.caption('Daftar awal pemeriksaan, diurutkan berdasarkan tunggakan pokok terbesar.')
                with right:
                    st.page_link('pages/executive_monitoring.py',label='Semua pemantauan',icon=':material/arrow_forward:')
            review_table(result['context']['review'])
