from src.ui.shared.assets import asset_text
from datetime import date
import streamlit as st
from src.auth.ui import page_guard,protected_action
from src.auth.actions import read_simulation_context
from src.ui.shared.paths import ROOT
from src.ui.executive.layout import load_styles
from src.ui.shared.formatters import rupiah, number
from src.ui.executive.simulation import (initialize,invalidate,search_changed,contract_changed,months_changed,slider_changed,
    reset_scenario,contract_html,result_html,comparison_html,schedule_html)
from src.services.simulation import simulate_principal,compare_scenarios

principal=page_guard('executive');initialize()
with st.container(key='executive_home'),st.container(key='executive_simulation_page'):
    progress=f"{(st.session_state['sim_month_slider']-1)/35*100}%"
    st.html('<style>'+asset_text(ROOT/'assets/css/simulation.css').replace('__SIM_PROGRESS__',progress)+'</style>')
    data=protected_action(read_simulation_context,code=st.session_state['sim_code'],search=st.session_state['sim_search'],expected_publication_id=st.session_state['sim_expected_publication'])
    st.html('<header class="bmt-page-header"><div><h1>Simulasi Jadwal</h1><p>Bandingkan estimasi pembayaran pokok berdasarkan jangka waktu yang dipilih.</p></div><span class="bmt-source-badge">Simulasi ilustratif</span></header><div class="sm-info">Simulasi tidak mengubah kontrak, kolektibilitas, NPF, daftar pemantauan, atau skor model.</div>')
    if not data['publication']:
        st.info('Belum ada publikasi aktif. Pilihan kontrak simulasi belum tersedia.');st.stop()
    if data['status']=='stale_scope':
        invalidate();st.warning('Publikasi aktif berubah. Muat ulang dan pilih kontrak dari publikasi terbaru.')
        st.button('Muat ulang pilihan',on_click=search_changed);st.stop()
    row=data['contract'];publication=data['publication']
    with st.container(key='simulation_contract',border=True):
        title,search=st.columns([3,2],vertical_alignment='center')
        with title:st.html('<h2>Pilih Kontrak Pembiayaan</h2><p class="sm-muted">Cari kode anonim untuk memuat pokok yang disimulasikan.</p>')
        with search:st.text_input('Cari kode pembiayaan',key='sim_search',on_change=search_changed,placeholder='Cari kode pembiayaan…',max_chars=64,icon=':material/search:')
        choices=list(dict.fromkeys([r['financing_code'] for r in data['choices']]+([st.session_state['sim_code']] if st.session_state['sim_code'] else [])))
        st.session_state['_sim_choice_publication']=publication['publication_id']
        st.selectbox('Kontrak pembiayaan',[None,*choices],key='sim_code',format_func=lambda c:c or 'Pilih kode pembiayaan',on_change=contract_changed)
        if row:st.html(contract_html(row))
        else:
            invalidate();st.info('Pilih kode pembiayaan dari publikasi aktif.' if not st.session_state['sim_code'] else 'Kontrak tidak ditemukan atau berasal dari versi lama. Pilih ulang kode dari hasil pencarian.')
        st.caption(f"{len(data['choices'])} dari {number(data['total_choices'])} hasil ditampilkan. Cari kode untuk mempersempit pilihan.")
    if row is None:st.stop()
    signature=(publication['publication_id'],row['financing_code'],row['outstanding_principal'],st.session_state['sim_months'],st.session_state['sim_start'])
    stored=st.session_state['sim_result']
    if stored and stored['signature']!=signature:invalidate();stored=None
    with st.container(key='simulation_workspace'):
        left,right=st.columns([5,7],gap='medium',vertical_alignment='top')
        with left,st.container(key='simulation_assumptions',border=True):
            st.html('<h2>Asumsi Perhitungan</h2>')
            st.text_input('Pokok yang disimulasikan',value=rupiah(row['outstanding_principal']),disabled=True)
            st.selectbox('Periode pembayaran',['Bulanan (per bulan)'],disabled=True)
            st.number_input('Jumlah periode (bulan)',min_value=1,max_value=36,step=1,key='sim_months',on_change=months_changed)
            st.slider('Pilih jumlah bulan',min_value=1,max_value=36,key='sim_month_slider',on_change=slider_changed,label_visibility='collapsed')
            st.caption('Rentang 1–36 bulan adalah fasilitas simulasi, bukan tenor yang disetujui BMT.')
            st.date_input('Tanggal pembayaran pertama',key='sim_start',value=None,min_value=date(1900,1,1),max_value=date(9999,12,31),format='DD/MM/YYYY',on_change=invalidate)
            st.caption('Tanggal input adalah awal skenario, bukan tanggal posisi laporan.')
            st.html('<div class="sm-info">Metode: pembagian pokok merata per bulan. Pembayaran reguler dibulatkan turun ke Rp0,01; sisanya dibayar pada periode terakhir.</div>')
            calculate,reset=st.columns([3,2],gap='small')
            with calculate:clicked=st.button('Hitung Simulasi',type='primary',width='stretch',icon=':material/play_arrow:')
            with reset:st.button('Reset',on_click=reset_scenario,width='stretch',icon=':material/restart_alt:')
            if clicked:
                page_guard('executive')
                try:
                    result=simulate_principal(row['outstanding_principal'],st.session_state['sim_months'],st.session_state['sim_start'])
                    alternatives=compare_scenarios(row['outstanding_principal'],st.session_state['sim_months'],st.session_state['sim_start'])
                    stored=dict(signature=signature,result=result,alternatives=alternatives);st.session_state['sim_result']=stored
                except ValueError as error:st.warning(str(error));invalidate();stored=None
        with right,st.container(key='simulation_results',border=True):
            if stored:
                st.html(result_html(stored['result'],publication=publication))
                if stored['result']['status']=='zero_outstanding':st.info('Outstanding pokok nol; tidak ada pembayaran pokok yang perlu dibagi.')
            else:st.html('<h2>Hasil Skenario</h2><p class="sm-muted">Isi tanggal pembayaran pertama lalu pilih Hitung Simulasi.</p><div class="sm-warning">Belum mencakup margin, denda, dan biaya lain.</div>')
    if stored:
        with st.container(key='simulation_comparison',border=True):
            st.html('<h2>Perbandingan Jangka Waktu</h2><p class="sm-muted">Alternatif pembagian pokok bulanan, bukan perubahan akad saat ini.</p>'+comparison_html(stored['alternatives'],publication=publication))
        with st.expander(f"Rincian pembayaran pokok ({stored['result']['months']} bulan)",expanded=True):
            st.caption('Jadwal simulasi, bukan transaksi aktual. Tanggal pertama adalah tanggal yang Anda isi.')
            st.html(schedule_html(stored['result']))
    with st.expander('Dasar perhitungan'):
        st.write('Pokok reguler = outstanding / jumlah bulan, dibulatkan turun ke dua desimal. Periode terakhir menyesuaikan sisa sehingga total pokok persis sama dengan outstanding; tunggakan tidak ditambahkan kembali.')
        st.write('Bulanan adalah asumsi kalender: tanggal awal merupakan pembayaran pertama. Jika tanggal awal merupakan akhir bulan, tanggal berikutnya mengikuti akhir bulan. Selain itu, hari awal dipertahankan dan dibatasi hari terakhir bulan bila perlu, lalu kembali ke hari awal pada bulan berikutnya.')
        st.write('Margin, denda, biaya, angsuran total, penghematan akad lama, dan perubahan skor tidak dihitung. Jangka waktu lebih panjang tidak membuktikan risiko berkurang.')
        st.caption(f"Publikasi {publication['publication_id']}, dataset {publication['dataset_version_id']}. Tanggal posisi: {'belum dikonfirmasi' if publication['position_date'] is None else str(publication['position_date'])}. Input tanggal skenario tidak mengubah metadata ini.")
    st.html('<p class="sm-footer">Hasil merupakan simulasi pembayaran pokok, bukan persetujuan penjadwalan kembali.</p>')
