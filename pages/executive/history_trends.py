from src.ui.shared.assets import asset_text
import streamlit as st
from src.auth.ui import page_guard,protected_action
from src.auth.actions import read_history_trends
from src.ui.shared.paths import ROOT
from src.ui.executive.layout import load_styles
from src.ui.shared.formatters import number
from src.ui.executive.history_trends import REASONS,export_text,position_text,reports_html,event_rows,decorative_icon
from html import escape

principal=page_guard('executive')
with st.container(key='executive_home'),st.container(key='executive_history_trends_page'):
    st.html('<style>'+asset_text(ROOT/'assets/css/history_trends.css')+'</style>')
    result=protected_action(read_history_trends);ready=result['readiness'];current=result['current']
    current_report=next((r for r in result['reports'] if current and r['publication_id']==current['publication_id']),None)
    meta=f'Ekspor data: {export_text(current_report)} · Tanggal posisi: {position_text(current_report)}' if current_report else 'Publikasi aktif belum tersedia'
    st.html('<header class="bmt-page-header"><div><div class="bmt-breadcrumb">Pimpinan / Riwayat &amp; Tren</div><h1>Riwayat &amp; Tren</h1><p>Tinjau perubahan kondisi portofolio berdasarkan laporan posisi yang tersedia.</p></div><span class="bmt-source-badge">'+escape(meta)+'</span></header>')
    with st.container(key='trend_availability',border=True):
        st.html(f'<div class="rt-availability"><div class="rt-document" aria-hidden="true">{decorative_icon("document")}</div><div><h2>{number(len(result["reports"]))} laporan pembiayaan aktif terpublikasi</h2><p>{escape(REASONS[ready["reason"]])} Riwayat unggah/publikasi bukan tren kondisi pembiayaan.</p></div><span class="rt-badge">Belum dapat dibandingkan</span></div>')
    with st.container(key='trend_periods',border=True):
        left,right=st.columns(2)
        with left:st.selectbox('Periode awal',[],placeholder='Pilih periode awal…',disabled=True)
        with right:st.selectbox('Periode pembanding',[],placeholder='Pilih periode pembanding…',disabled=True)
        st.html('<p class="rt-period-note">Perbandingan memerlukan minimal dua laporan posisi terkonfirmasi dengan cakupan dan definisi yang sebanding.</p>')
    with st.container(key='trend_panel',border=True):
        title,metric=st.columns([3,2],vertical_alignment='center')
        with title:st.html('<h2>Perubahan Portofolio</h2><p class="rt-muted">Visualisasi tren agregat antarperiode laporan posisi.</p>')
        with metric:st.segmented_control('Metrik tren',['Outstanding','Tunggakan Pokok','NPF'],default='Outstanding',disabled=True,label_visibility='collapsed',help='Belum tersedia pasangan snapshot dengan kesebandingan terverifikasi.')
        with st.container(key='trend_empty'):
            st.html('<div class="rt-empty-copy"><div class="rt-empty-icon" aria-hidden="true">'+decorative_icon('trend')+'</div><h3>Data antarperiode belum tersedia</h3><p>Grafik memerlukan laporan pembanding, tanggal posisi terkonfirmasi, dan cakupan yang disahkan sebanding.</p></div>')
            st.page_link(ROOT/'pages/executive/quality.py',label='Lihat Kondisi Saat Ini',icon=':material/arrow_forward:')
    with st.container(key='trend_reports',border=True):
        st.html('<h2>Laporan Posisi yang Tersedia</h2><p class="rt-muted">Laporan pembiayaan aktif terpublikasi yang tercatat di sistem.</p>'+reports_html(result['reports'],current))
    with st.container(key='trend_history_details'):
        with st.expander('Kapan tren dapat ditampilkan?',icon=':material/help:'):
            st.write('Minimal dua tanggal posisi berbeda harus terkonfirmasi. Unggahan berulang/file yang sama bukan periode baru. Tanggal publikasi, unggah, realisasi, dan komputer tidak menggantikan posisi.')
            st.write('Cakupan dan definisi indikator harus disahkan sebanding. Skema saat ini belum menyediakan kontrak pengesahan cakupan tersebut; kesamaan jumlah kontrak/versi skema saja tidak membuktikannya. Karena itu mesin perbandingan/garis tren belum diaktifkan, termasuk jika hanya tanggal yang diisi.')
            st.write('Perubahan portofolio tidak otomatis dijelaskan sebagai pembayaran, pencairan, atau migrasi kolektibilitas. Analisis per kontrak memerlukan pengenal konsisten dan pemeriksaan sumber.')
            st.caption(f"Laporan terpublikasi: {ready['published_reports']}; tanggal posisi berbeda terkonfirmasi: {ready['distinct_confirmed_positions']}; posisi belum terkonfirmasi: {ready['unknown_positions']}.")
        with st.expander('Riwayat pencatatan, unggah, dan publikasi',icon=':material/history:',
                         key='trend_event_history',on_change='rerun') as history:
            if history.open:
                st.caption('Metadata peristiwa dalam UTC; bukan tanggal posisi atau tren pembiayaan. Kandidat ready tidak termasuk laporan terpublikasi di atas.')
                if result['inventory']:st.dataframe(event_rows(result['inventory']),hide_index=True,width='stretch')
                else:st.info('Belum ada versi pembiayaan aktif yang tercatat.')
    st.html('<p class="rt-footer">Analisis riwayat dan tren membutuhkan konsistensi definisi dan konfirmasi tanggal posisi laporan.</p>')
