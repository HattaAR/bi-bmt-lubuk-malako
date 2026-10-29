"""Executive sidebar, header, filters and stylesheet from referensi desain UI."""
from collections import Counter
from html import escape
import streamlit as st
from src.ui.shared.assets import asset_text,asset_uri
from src.ui.shared.paths import ROOT
from src.ui.shared.design import workspace_css
CATEGORIES = {"L": ("Lancar", "#134e2a"), "KL": ("Kurang Lancar", "#F59E0B"), "D": ("Diragukan", "#F97316"), "M": ("Macet", "#F43F5E"), "UNKNOWN": ("Tidak dikenali", "#64748B")}
FILTER_KEYS = ("executive_marketing", "executive_sector")

def modern_shell_css():
    """Approved opt-in shell; other executive pages and login keep their styling."""
    return asset_text(ROOT/'assets/css/executive_modern_shell.css')

def load_styles():
    face = ''
    for family, file in (('BmtExecutiveInter','Inter-latin.woff2'),):
        font=asset_uri(ROOT/'assets/fonts'/file,'font/woff2')
        face += '@font-face{font-family:' + family + ';src:url('+font+') format("woff2");font-weight:100 900;font-display:swap;}'
    st.html('<style>'+face+workspace_css()+asset_text(ROOT/'assets/css/executive.css')+'</style>')

def executive_sidebar(principal, on_logout,active_title='Beranda'):
    with st.sidebar, st.container(key='executive_sidebar', gap=None):
        logo=asset_uri(ROOT/'assets/logo.png','image/png')
        st.html(f'<div class="bmt-brand"><img src="{logo}" width="40" height="40" style="width:40px;height:40px;object-fit:contain" alt="Logo BMT"><div><strong>BI BMT Lubuk Malako</strong><span>Pimpinan / Eksekutif</span></div></div>')
        search = st.text_input('Cari menu', placeholder='Cari menu & laporan…', icon=':material/search:', label_visibility='collapsed', key='executive_menu_search')
        sections=(('primary','NAVIGASI UTAMA',(('home','Beranda','dashboard'),('quality','Kualitas Portofolio','bar_chart'),('monitoring','Pemantauan & Prioritas','warning'),('concentration','Konsentrasi Portofolio','pie_chart'),('marketing','Portofolio Marketing','groups'))),
                  ('analysis','ANALISIS & PROYEKSI',(('historical','Analisis Historis','monitoring'),('simulation','Simulasi Jadwal','calendar_month'),('history_trends','Riwayat & Tren','timeline'),('methodology','Model & Metodologi','science'))))
        for section,heading,links in sections:
            with st.container(key='executive_'+section+'_heading',gap=None):
                st.html('<p class="bmt-nav-group">'+heading+'</p>')
            for key,title,icon in links:
                if search.strip().casefold() not in title.casefold():continue
                with st.container(key='executive_'+key+'_link',gap=None):
                    if title==active_title:
                        with st.container(key='executive_current_nav',gap=None):
                            st.page_link(ROOT/f'pages/executive/{key}.py',label=title,icon=f':material/{icon}:')
                    else:st.page_link(ROOT/f'pages/executive/{key}.py',label=title,icon=f':material/{icon}:')
        if 'admin' in principal.roles:
            st.caption('PENGELOLAAN DATA')
            st.page_link(ROOT / 'pages/admin/upload.py', label='Unggah & validasi', icon=':material/upload:')
            st.page_link(ROOT / 'pages/admin/history.py', label='Riwayat unggahan', icon=':material/history:')
        with st.container(key='executive_account'):
            profile, action = st.columns([5,1], vertical_alignment='center', gap='small')
            with profile:
                st.html(f'<div class="bmt-account"><span class="bmt-avatar">{escape(principal.display_name[:2].upper())}</span><div><strong>{escape(principal.display_name)}</strong><small>Pimpinan BMT Lubuk Malako</small></div></div>')
            with action:
                st.button('Keluar', icon=':material/logout:', on_click=on_logout, help='Keluar dari sesi', width='content')

def reset_filters():
    for key in FILTER_KEYS:
        st.session_state[key] = None


def dimension_filter(label, options, key, *, on_change=None):
    labels = {row['id']: row['label'] for row in options}
    counts = Counter(labels.values())
    labels = {identifier: (f'{label} · #{identifier}' if counts[label] > 1 else label) for identifier,label in labels.items()}
    if st.session_state.get(key) not in {None, *labels}:
        reset_filters()
        if on_change:on_change()
        st.rerun()
    return st.selectbox(label, [None, *labels], key=key, placeholder='Semua ' + label,
                       on_change=on_change,
                       format_func=lambda value: 'Semua ' + label if value is None else labels[value])

def filters(context):
    with st.container(key='executive_filters', border=True):
        columns = st.columns([1, 1, 1], vertical_alignment='center')
        for column, label, options, key in zip(columns, ('Marketing','Sektor'), (context['marketing'],context['sectors']), FILTER_KEYS):
            with column:
                dimension_filter(label, options, key)
        with columns[2]:
            st.button('Reset filter', on_click=reset_filters, width='content', icon=':material/restart_alt:')

def header(principal, result, *, title='Beranda', description='Ringkasan portofolio dan pembiayaan untuk ditinjau.'):
    p = result['publication']
    badges = ''
    if p:
        position = 'Tanggal posisi belum dikonfirmasi' if p['position_date'] is None or p['position_date_status'] != 'confirmed' else f'Tanggal posisi: {p["position_date"]:%d-%m-%Y}'
        badges = f'<span class="bmt-source-badge"><i></i>{escape(position)}</span>'
    st.html(f'<header class="bmt-page-header"><div><div class="bmt-breadcrumb">Pimpinan <span>›</span> {escape(title)}</div><h1>{escape(title)}</h1><p>{escape(description)}</p></div><div class="bmt-header-badges">{badges}</div></header>')






