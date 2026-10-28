"""Shared presentation following the project's Beranda referensi desain UI."""
from decimal import Decimal
from collections import Counter
import base64
from html import escape
from urllib.parse import quote
from pathlib import Path
import streamlit as st
from src.ui.assets import asset_text,asset_uri
from src.ui.motion import percent_markup,scope_attributes

ROOT = Path(__file__).resolve().parents[2]
CATEGORIES = {"L": ("Lancar", "#134e2a"), "KL": ("Kurang Lancar", "#F59E0B"), "D": ("Diragukan", "#F97316"), "M": ("Macet", "#F43F5E"), "UNKNOWN": ("Tidak dikenali", "#64748B")}
FILTER_KEYS = ("executive_marketing", "executive_sector")

def number(value, places=0):
    return "—" if value is None else f"{value:,.{places}f}".translate(str.maketrans({",": ".", ".": ","}))

def rupiah(value):
    return "—" if value is None else "Rp" + number(value, 2)

def compact_rupiah(value):
    if value is None:
        return "—"
    for scale, label in ((Decimal('1000000000000'), 'triliun'), (Decimal('1000000000'), 'miliar'), (Decimal('1000000'), 'juta')):
        if abs(value) >= scale:
            return 'Rp' + number(value / scale, 2) + ' ' + label
    return rupiah(value)

def percent(value):
    return "—" if value is None else number(value, 2) + "%"

def load_styles():
    face = ''
    for family, file in (('BmtExecutiveInter','Inter-latin.woff2'),):
        font=asset_uri(ROOT/'assets/fonts'/file,'font/woff2')
        face += '@font-face{font-family:' + family + ';src:url('+font+') format("woff2");font-weight:100 900;font-display:swap;}'
    st.html('<style>'+face+asset_text(ROOT/'assets/css/executive.css')+'</style>')

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
                            st.page_link(ROOT/f'pages/executive_{key}.py',label=title,icon=f':material/{icon}:')
                    else:st.page_link(ROOT/f'pages/executive_{key}.py',label=title,icon=f':material/{icon}:')
        if 'admin' in principal.roles:
            st.caption('PENGELOLAAN DATA')
            st.page_link(ROOT / 'pages/admin_upload.py', label='Unggah & validasi', icon=':material/upload:')
            st.page_link(ROOT / 'pages/admin_history.py', label='Riwayat unggahan', icon=':material/history:')
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

def header(principal, result, *, title='Beranda', description='Pantau kualitas portofolio dan pembiayaan yang perlu ditinjau secara berkala.'):
    p = result['publication']
    badges = ''
    if p:
        position = 'Tanggal posisi belum dikonfirmasi' if p['position_date'] is None or p['position_date_status'] != 'confirmed' else f'Tanggal posisi: {p["position_date"]:%d-%m-%Y}'
        badges = f'<span class="bmt-source-badge"><i></i>{escape(position)}</span>'
    st.html(f'<header class="bmt-page-header"><div><div class="bmt-breadcrumb">Pimpinan <span>›</span> {escape(title)}</div><h1>{escape(title)}</h1><p>{escape(description)}</p></div><div class="bmt-header-badges">{badges}</div></header>')

def _card_icon(kind):
    # Local SVG paths from the paired referensi desain UI; st.html keeps image data URIs.
    paths = {'hero': 'M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z',
             'arrears': 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
             'npf': 'M13 17h8m0 0V9m0 8l-8-8-4 4-6-6'}
    color = {'hero':'#a7f3d0','arrears':'#d97706','npf':'#e11d48'}[kind]
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="{paths[kind]}"/></svg>'
    return '<img alt="" aria-hidden="true" src="data:image/svg+xml,' + quote(svg, safe='') + '">'


def summary_cards(result):
    k = result['kpis']
    specs = [
        ('Total Outstanding', compact_rupiah(k['outstanding_principal']), rupiah(k['outstanding_principal']), f'{number(k["active_contracts"])} kontrak aktif', 'Saldo pokok pembiayaan dalam cakupan data', 'Lihat komposisi', '#komposisi', 'hero', '▤'),
        ('Tunggakan Pokok', compact_rupiah(k['overdue_principal']), rupiah(k['overdue_principal']), f'{number(k["contracts_with_arrears"])} kontrak menunggak', 'Pokok tertunggak dalam cakupan data', 'Tinjau pembiayaan', '#pembiayaan-ditinjau', 'arrears', '!'),
        ('Rasio NPF', percent(k['npf_percent']), f'Outstanding KL+D+M: {rupiah(k["npf_outstanding"])}', f'{number(result["npf_contracts"])} kontrak KL, D, M', 'Outstanding KL, D, M dibagi total outstanding cakupan data', 'Lihat kolektibilitas', '#komposisi', 'npf', '↘'),
    ]
    cards = []
    for label,value,full,badge,description,action,target,kind,icon in specs:
        display_value=percent_markup(k['npf_percent'],value) if kind=='npf' else escape(value)
        cards.append(f'<article class="bmt-kpi bmt-kpi-{kind}"><div class="bmt-kpi-top"><span class="bmt-kpi-label"><i aria-hidden="true">{_card_icon(kind)}</i>{label}</span><span class="bmt-pill">{escape(badge)}</span></div><strong class="bmt-kpi-value" title="{escape(full)}">{display_value}</strong><p>{escape(description)}</p><a href="{target}" target="_self">{action}<span aria-hidden="true"> →</span></a></article>')
    st.html('<section '+scope_attributes(result,'Beranda')+' class="bmt-kpi-grid" aria-label="Ringkasan portofolio">' + ''.join(cards) + '</section>')

def composition_rows(result):
    return [{'Kategori': CATEGORIES[row['code']][0], 'Jumlah kontrak': row['contracts'], 'Outstanding': rupiah(row['outstanding_principal']), 'Persentase outstanding': percent(row['outstanding_share_percent'])} for row in result['composition'] if row['code'] != 'UNKNOWN' or row['contracts']]

def composition_chart(result, basis='Outstanding'):
    rows = []
    for row in result['composition']:
        if row['code'] == 'UNKNOWN' and not row['contracts']:
            continue
        label,color = CATEGORIES[row['code']]
        share = row['outstanding_share_percent'] if basis == 'Outstanding' else row['contract_share_percent']
        width = max(Decimal(0), min(Decimal(100), share or Decimal(0)))
        text = f'{number(row["contracts"])} kontrak ({percent(row["contract_share_percent"])}) · {rupiah(row["outstanding_principal"])} ({percent(row["outstanding_share_percent"])})'
        rows.append(f'<div class="bmt-composition-row"><div class="bmt-composition-label"><span><i style="background:{color}"></i>{escape(label)}</span><strong>{escape(text)}</strong></div><div class="bmt-track" role="img" aria-label="{escape(label+": "+text)}"><div style="width:{width}%;background:{color}"></div></div></div>')
    st.html('<div '+scope_attributes(dict(result,metric=basis),'Beranda')+' class="bmt-composition">' + ''.join(rows) + '</div><div class="bmt-chart-footer"><span>Perhitungan mengacu pada satu publikasi dan cakupan filter.</span><strong>Total: ' + number(result['kpis']['active_contracts']) + ' kontrak · ' + rupiah(result['kpis']['outstanding_principal']) + '</strong></div>')

def review_table(review):
    body = []
    for row in review['rows']:
        code = row['collectibility_code'] if row['collectibility_code'] in CATEGORIES else 'UNKNOWN'
        label,color = CATEGORIES[code]
        maturity = row['maturity_date'].strftime('%d-%m-%Y') if row['maturity_date'] else '—'
        body.append('<tr>' + ''.join(f'<td>{value}</td>' for value in (
            escape(row['financing_code']), escape(row['marketing_name'] or 'Tidak diketahui'),
            f'<span class="bmt-category bmt-category-{code.lower()}">{escape(label)}</span>',
            rupiah(row['outstanding_principal']), '<span class="bmt-overdue">'+rupiah(row['overdue_principal'])+'</span>',
            maturity, escape(row['review_reason']), '<span class="bmt-unavailable" title="Halaman detail belum tersedia">Belum tersedia</span>')) + '</tr>')
    if not body:
        body.append('<tr><td colspan="8">Tidak ada pembiayaan yang perlu ditinjau dalam cakupan ini.</td></tr>')
    headers = ('Kode Pembiayaan','Marketing','Kolektibilitas','Outstanding','Tunggakan Pokok','Jatuh Tempo','Alasan Ditampilkan','Detail')
    st.html('<div class="bmt-table-scroll" tabindex="0" role="region" aria-label="Tabel pembiayaan untuk ditinjau"><table class="bmt-review-table"><thead><tr>' + ''.join('<th scope="col">'+h+'</th>' for h in headers) + '</tr></thead><tbody>' + ''.join(body) + '</tbody></table></div><div class="bmt-table-footer"><span>Kode anonim terikat versi dataset; bukan nomor rekening.</span><span>Menampilkan ' + str(len(review['rows'])) + ' dari ' + number(review['total']) + ' kontrak</span></div>')
