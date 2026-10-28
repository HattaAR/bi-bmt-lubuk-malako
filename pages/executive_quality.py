import streamlit as st

from src.auth.actions import read_executive_kpis
from src.auth.ui import page_guard, protected_action
from src.ui.executive import FILTER_KEYS, filters, header, load_styles
from src.ui.portfolio_quality import render_quality

principal = page_guard('executive')
# Shared shell key intentionally retains the verified native sidebar/layout behavior.
with st.container(key='executive_home'), st.container(key='executive_quality'):
    result = protected_action(read_executive_kpis,
                              marketing_id=st.session_state.get(FILTER_KEYS[0]),
                              sector_id=st.session_state.get(FILTER_KEYS[1]), include_context=True)
    header(principal, result, title='Kualitas Portofolio',
           description='Komposisi kolektibilitas, outstanding, dan tunggakan pembiayaan aktif.')
    if result['publication'] is None:
        st.info('Belum ada publikasi aktif. Ringkasan tersedia setelah data diterbitkan administrator.')
    else:
        filters(result['context'])
        reasons = {'empty_selection':'Tidak ada kontrak pada kombinasi filter ini. Ubah pilihan atau reset filter.',
                   'zero_outstanding':'NPF tidak tersedia karena total outstanding nol.',
                   'unknown_collectibility':'NPF belum lengkap karena terdapat kategori kolektibilitas tidak dikenali.'}
        if result['npf_reason'] in reasons:
            st.info(reasons[result['npf_reason']])
        render_quality(result)
