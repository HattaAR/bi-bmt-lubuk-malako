"""Admin components following the paired referensi desain UI, with native actions."""
from html import escape
from urllib.parse import quote
import streamlit as st
import pymysql
from src.ui.executive import ROOT,number,rupiah
from src.ui.assets import asset_text,asset_uri

WARNING_IMPACT={
 'POSITION_DATE_UNKNOWN':'BI statis dapat digunakan. Tren posisi dan pengingat berbasis tanggal posisi belum tersedia.',
 'MATURITY_BEFORE_REALIZATION':'Kontrak dan nominal dipertahankan; jatuh tempo analitik/durasi NULL, input model tidak layak.',
 'DATE_INVALID':'Tanggal analitik/durasi tidak valid menjadi NULL; nominal tetap dipertahankan.',
 'GROUP_UNMAPPED':'Kontrak disimpan sebagai belum terpetakan; rincian kelompok perlu ditinjau.',
 'COLLECTIBILITY_UNKNOWN':'Kategori tidak dianggap Lancar. NPF tidak dapat dinyatakan lengkap.',
 'OPTIONAL_NUMBER_INVALID':'Atribut opsional menjadi NULL; tidak digunakan untuk analisis/model terkait.',
 'INSTALLMENT_SEQUENCE_UNVERIFIED':'Urutan angsuran sumber tidak digunakan untuk indikator maupun fitur model.',
 'MARGIN_ARREARS_ALL_ZERO':'Nilai nol bukan bukti tidak ada tunggakan margin; indikator ini tidak digunakan.',
 'REFERENCE_VALUE_INVALID':'Pasangan kode/nama kosong atau bukan teks tidak digunakan dalam kamus.',
}


def icon(kind):
    paths={'file':'M14 2H6v20h12V6zM14 2v5h5M9 12h6m-6 4h6',
           'tune':'M4 6h16M4 12h16M4 18h16M8 3v6m8 0v6m-8 0v6',
           'check':'M20 6 9 17l-5-5','sync':'M4 7h16m-4-4 4 4-4 4M20 17H4m4-4-4 4 4 4',
           'upload':'M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6'}
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#166547" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="{paths.get(kind,paths["file"])}"/></svg>'
    return '<img alt="" aria-hidden="true" width="22" height="22" src="data:image/svg+xml,'+quote(svg,safe='')+'">'


def load_styles():st.html('<style>'+asset_text(ROOT/'assets/css/admin.css')+'</style>')


def admin_sidebar(principal,on_logout,active_title):
    load_styles()
    with st.sidebar,st.container(key='admin_shell',gap=None):
        logo=asset_uri(ROOT/'assets/logo.png','image/png')
        st.html(f'<div class="adm-brand"><img src="{logo}" width="40" height="40" alt="Logo BMT"><div><strong>BI BMT Lubuk Malako</strong><span>● Admin Sistem BI</span></div></div>')
        st.html('<p class="adm-nav-heading">PENGELOLAAN DATA</p>')
        for file,label,symbol,title in [('admin_upload','Unggah & Validasi Data','upload_file','Unggah & validasi'),('admin_history','Riwayat Unggahan','history','Riwayat unggahan')]:
            with st.container(key='admin_nav_'+file,gap=None):
                if title==active_title:
                    with st.container(key='admin_current_nav',gap=None):st.page_link(ROOT/f'pages/{file}.py',label=label,icon=f':material/{symbol}:')
                else:st.page_link(ROOT/f'pages/{file}.py',label=label,icon=f':material/{symbol}:')
        if 'executive' in principal.roles:st.page_link(ROOT/'pages/executive_home.py',label='Beranda Pimpinan',icon=':material/dashboard:')
        with st.container(key='admin_account'):
            left,right=st.columns([5,1],gap='small',vertical_alignment='center')
            with left:st.html(f'<div class="adm-profile"><span>{escape(principal.display_name[:2].upper())}</span><div><strong>{escape(principal.display_name)}</strong><small>KSPPS BMT Lubuk Malako</small></div></div>')
            with right:st.button('Keluar',icon=':material/logout:',on_click=on_logout,help='Keluar dari sistem admin',key='admin_logout')


def header():
    st.html('<header class="adm-header"><div><div class="adm-breadcrumb">Admin / Unggah &amp; Validasi Data</div><h1>Unggah &amp; Validasi Data</h1><p>Periksa file pembiayaan sebelum digunakan pada dashboard.</p></div><span class="adm-badge">● Workspace Admin Aktif</span></header>')


def stepper(stage):
    labels=[('Unggah File','Informasi laporan & berkas Excel'),('Periksa Data','Validasi struktur & anomali'),('Terbitkan','Pembaruan ke dashboard BI')]
    items=[]
    for i,(title,description) in enumerate(labels,1):
        status='active' if i==stage else 'done' if i<stage else 'locked'
        items.append(f'<div class="adm-step {status}" '+('aria-current="step"' if i==stage else '')+f'><span class="adm-step-number">{"✓" if i<stage else i}</span><div><strong>Tahap {i}: {title}</strong><small>{escape(description)}</small></div></div>')
    st.html('<section class="adm-stepper" aria-label="Tahapan unggah dan validasi">'+''.join(items)+'</section>')


def section_heading(title,kind='file',description=None,badge=None):
    st.html('<div class="adm-section-title"><div>'+icon(kind)+'<div><h2>'+escape(title)+'</h2>'+
            ('<p>'+escape(description)+'</p>' if description else '')+'</div></div>'+
            ('<span class="adm-badge">'+escape(badge)+'</span>' if badge else '')+'</div>')


def note(text,*,warning=True):
    st.html('<div class="adm-note '+('warning' if warning else '')+'">'+escape(text)+'</div>')


def file_summary(candidate):
    meta=candidate.report_metadata
    entries=[('Nama Laporan',meta['report_name']),('File',candidate.active_source.path.name),
             ('Sheet',candidate.active_source.sheet),('Jenis Dataset','Pembiayaan aktif'),
             ('Baris',number(candidate.summary['rows'])),('Waktu Ekspor',meta['export_date'] or meta['export_period_text'] or 'Belum diketahui'),
             ('Tanggal Posisi',meta['position_date'] or 'Belum diketahui'),('Cakupan Entitas',meta['scope_description'])]
    st.html('<dl class="adm-report-grid">'+''.join('<div><dt>'+escape(k)+'</dt><dd>'+escape(v)+'</dd></div>' for k,v in entries)+'</dl>')


def findings_table(findings,*,validated=False):
    rows=[]
    if validated:
        for title,text in [('Struktur dan kolom wajib','Seluruh kolom wajib sumber aktif dan kamus tersedia.'),('Format nominal inti','Nominal awal, outstanding, dan tunggakan pokok valid pada presisi Decimal.'),('Identitas & keunikan rekening','Pengenal teks dipertahankan; tidak ada rekening berulang setelah normalisasi.')]:
            rows.append('<tr><td><strong>'+title+'</strong></td><td><span class="adm-status">Lulus</span></td><td>'+text+'</td></tr>')
    labels={'POSITION_DATE_UNKNOWN':'Tanggal posisi laporan','MATURITY_BEFORE_REALIZATION':'Urutan tanggal kontrak',
            'DATE_INVALID':'Format tanggal','GROUP_UNMAPPED':'Pemetaan marketing/sektor','COLLECTIBILITY_UNKNOWN':'Kategori kolektibilitas',
            'OPTIONAL_NUMBER_INVALID':'Atribut nominal/tenor opsional','INSTALLMENT_SEQUENCE_UNVERIFIED':'Urutan angsuran sumber',
            'MARGIN_ARREARS_ALL_ZERO':'Tunggakan margin','ACCOUNT_DUPLICATE':'Keunikan rekening','ACCOUNT_INVALID':'Format rekening',
            'CORE_MONEY_INVALID':'Nominal inti tidak valid','INPUT_INVALID':'Format, sheet, atau metadata sumber'}
    for f in findings:
        status='Penghambat' if f.severity=='blocking' else 'Perlu ditinjau' if f.severity=='warning' else 'Informasi'
        text=WARNING_IMPACT.get(f.rule_code, 'Nilai/struktur tidak memenuhi aturan validasi. Perbaiki sumber dan jalankan pemeriksaan ulang.' if f.severity=='blocking' else f.message)
        source=(f'Baris Excel {f.source_row_number} · ' if f.source_row_number else '')+(f.field_name or 'Laporan')
        rows.append(f'<tr><td><strong title="{escape(f.rule_code)}">{escape(labels.get(f.rule_code,f.rule_code))}</strong><small>{escape(source)}</small></td><td><span class="adm-status {f.severity}">{status}</span></td><td>{escape(text)}</td></tr>')
    st.html('<div class="adm-table-scroll"><table class="adm-table"><thead><tr><th>Pemeriksaan</th><th>Status</th><th>Temuan & dampak penggunaan</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>')


def preview_table(candidate):
    rows=[]
    for r in candidate.rows[:5]:
        rows.append('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in (f'Baris {r.source_row_number}',candidate.marketing.get(r.marketing_code,'Belum terpetakan'),r.category,rupiah(r.money['saldo_nominatif']),rupiah(r.money['tunggakan_pokok']),r.maturity_date.isoformat() if r.maturity_date else '—'))+'</tr>')
    st.html('<div class="adm-table-scroll"><table class="adm-table"><thead><tr><th>Lineage</th><th>Marketing</th><th>Kolektibilitas</th><th>Outstanding</th><th>Tunggakan</th><th>Jatuh Tempo</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>')


def call(action,*args,**kwargs):
    from src.auth.session import AuthenticationRequired,AccessDenied
    from src.auth.service import AuthenticationUnavailable
    from src.database.publication_checks import PublicationError
    try:return action(st.session_state,*args,**kwargs)
    except (AuthenticationRequired,AccessDenied,AuthenticationUnavailable):
        st.error('Akses berubah atau sesi berakhir. Masuk kembali melalui halaman utama.')
    except PublicationError as error:st.error(str(error))
    except (pymysql.MySQLError,OSError,ValueError):
        st.error('Operasi belum dapat dikonfirmasi. Periksa ulang sumber atau preview sebelum mencoba kembali.')
    st.stop()


def footer():st.html('<footer class="adm-footer">Sistem Business Intelligence KSPPS BMT Lubuk Malako • Modul Administrasi &amp; Unggah Data</footer>')
