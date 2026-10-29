"""Presentation aligned with the three Model & Metodologi referensi desain UI."""
from html import escape
from urllib.parse import quote
import streamlit as st
from src.services.methodology import ALGORITHMS,METRICS,evaluation_rows
from src.services.methodology import inspect_evidence,filter_definitions,EVALUATIONS
from src.auth.ui import protected_action
from src.auth.actions import read_history_trends
from src.ui.shared.assets import asset_text
from src.ui.shared.paths import ROOT
from src.ui.executive.history_trends import position_text,export_text

TABS=(':material/verified_user: Penggunaan Skor',':material/analytics: Evaluasi Model',':material/dataset: Data & Definisi')


def icon(name):
    paths={
        'shield':'<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Z"/><path d="m8 12 3 3 5-6"/>',
        'eye':'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
        'book':'<path d="M12 5v15M3 4c4-1 6 0 9 1 3-1 5-2 9-1v15c-4-1-6 0-9 1-3-1-5-2-9-1Z"/>',
        'database':'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
        'settings':'<path d="M4 6h16M4 12h16M4 18h16M8 3v6M16 9v6M10 15v6"/>',
    }
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#047857" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'+paths[name]+'</svg>'
    return '<img class="mm-icon" alt="" aria-hidden="true" src="data:image/svg+xml,'+quote(svg,safe='')+'">'


def table(headers,rows,*,label,cls=''):
    body=''.join('<tr>'+''.join('<td>'+value+'</td>' for value in row)+'</tr>' for row in rows)
    return '<div class="mm-table-scroll '+cls+'" role="region" tabindex="0" aria-label="'+escape(label)+'"><table><thead><tr>'+''.join('<th scope="col">'+escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+body+'</tbody></table></div>'


def usage_html():
    return '''<h2>Skor sebagai informasi pendukung</h2>
<p class="mm-lead">Rancangan penelitian menggunakan pola penyelesaian pembiayaan historis. Jika integrasinya kelak tervalidasi, skor dapat melengkapi pemeriksaan kondisi aktual.</p>
<div class="mm-two mm-divider"><section class="mm-soft"><h3>'''+icon('shield')+'''Yang dianalisis</h3><ul><li>Target proyek: selesai setelah jatuh tempo awal kontrak (kelas 1); sebelum/tepat waktu (kelas 0).</li><li>Tanggal harus valid. Target ini bukan kolektibilitas resmi atau frekuensi keterlambatan angsuran.</li></ul></section>
<section class="mm-soft"><h3>'''+icon('eye')+'''Cara membacanya</h3><ul><li>Makna dan arah skor mengikuti model yang terverifikasi.</li><li>Probabilitas memerlukan bukti kalibrasi; skor mentah belum tentu probabilitas.</li><li>Skor bukan kepastian keterlambatan. Skor kosong bukan risiko rendah.</li></ul></section></div>
<div class="mm-divider"><h3>Alur Penggunaan Skor</h3><ol class="mm-steps"><li><b>1</b><div><strong>Tinjau Aktual</strong><p>Periksa tunggakan dan kolektibilitas sumber terlebih dahulu.</p></div></li><li><b>2</b><div><strong>Gunakan Skor Tambahan</strong><p>Hanya bila tersedia, terverifikasi, dan input memenuhi syarat.</p></div></li><li><b>3</b><div><strong>Konfirmasi Petugas</strong><p>Konfirmasikan kondisi sebelum menentukan tindak lanjut.</p></div></li></ol></div>
<p class="mm-warning">Bukti eksperimen belum tersedia untuk menetapkan model terpilih atau menilai kinerjanya. Skor pembiayaan aktif belum diaktifkan.</p>'''


def metadata_html(evidence):
    label='Berkas ditemukan; belum diverifikasi' if evidence['status']=='unverified' else 'Bukti model belum tersedia'
    cells=''.join('<div><span>'+name+'</span><strong>—</strong></div>' for name in ('Model yang digunakan','Versi model','Tanggal pelatihan'))
    return '<div class="mm-panel-heading"><h3>Status &amp; Metadata Model</h3><span class="mm-status">Integrasi belum aktif</span></div><div class="mm-metadata">'+cells+'</div><p class="mm-muted">'+label+'. Tanda — berarti belum dapat diverifikasi dari berkas proyek, bukan berarti pelatihan belum pernah dilakukan.</p>'


def metrics_html(evidence,mode):
    rows=[[escape(row['algorithm']),*['<span class="mm-missing" title="Hasil belum terverifikasi">—</span>' if row[key] is None else escape(str(row[key])) for key in METRICS]] for row in evaluation_rows(evidence,mode)]
    return table(('Algoritma','Accuracy','Precision','Recall','F1-score','ROC-AUC'),rows,label='Hasil evaluasi '+mode,cls='mm-evaluation-table')


def configuration_html():
    rows=[[escape(name),*['<span class="mm-missing">—</span>']*4] for name in ALGORITHMS]
    return table(('Algoritma','Paket Fitur','Sasaran Tuning','Threshold','Parameter'),rows,label='Konfigurasi belum terverifikasi')


def sources_html(current_report):
    actual=' / '.join(s['filename']+' · '+s['sheet'] for s in current_report['sources']) if current_report else ''
    active_label=actual or ('Sumber aktif belum tercatat' if current_report else '1.XLS (sumber aktif yang ditetapkan)')
    active_note='Mengikuti publikasi aktif; lihat status tanggal posisi di bawah.' if current_report else 'Belum ada publikasi aktif. Kandidat ready tidak digunakan sebagai pengganti.'
    rows=[
        [f'<code>{escape(active_label)}</code>','Pembiayaan aktif','KPI dan pemantauan portofolio',escape(active_note)],
        ['<code>SQLRESULT.XLS</code>','Pembiayaan yang telah selesai','Analisis historis; sumber penelitian yang ditetapkan','Publikasi terpisah. Selesai dibandingkan dengan jatuh tempo awal; bukan pengganti data aktif.'],
        ['<code>SQLRESULT1.XLS</code>','Kamus marketing/sektor','Pemetaan kode_group1/2 ke deskripsi_group1/2','Join kode many-to-one. Baris kontraknya tidak digabung dengan sumber aktif.'],
    ]
    return table(('Sumber','Isi Data','Penggunaan','Catatan'),rows,label='Sumber data dan perannya',cls='mm-source-table')


def definitions_html(rows):
    return table(('Indikator','Pengertian / Perhitungan','Catatan Penggunaan'),[[escape(v) for v in row] for row in rows],label='Definisi indikator',cls='mm-definition-table')

def render():
    with st.container(key='executive_home'),st.container(key='executive_methodology_page'):
        st.html('<style>'+asset_text(ROOT/'assets/css/methodology.css')+'</style>')
        context=protected_action(read_history_trends)
        current=context['current']
        report=next((r for r in context['reports'] if current and r['publication_id']==current['publication_id']),None)
        evidence=inspect_evidence()
        with st.container(key='methodology_header'):
            title,download=st.columns([4,1],vertical_alignment='center')
            with title:st.html('<header class="bmt-page-header"><div><div class="bmt-breadcrumb">Pimpinan / Model &amp; Metodologi</div><h1>Model &amp; Metodologi</h1><p>Pahami dasar analisis, hasil evaluasi, dan batas penggunaan informasi.</p></div></header>')
            with download:st.download_button('Dokumentasi Model',(ROOT/'docs/MODEL_METHODOLOGY.md').read_bytes(),file_name='model-metodologi.md',mime='text/markdown',icon=':material/description:')
        use,evaluate,data=st.tabs(TABS,key='methodology_tabs',on_change='rerun')
        if use.open:
            with use,st.container(key='methodology_usage_content'):
                with st.container(key='methodology_usage',border=True):st.html(usage_html())
                with st.container(key='methodology_status',border=True):
                    st.html(metadata_html(evidence))
                    with st.expander('Fitur, preprocessing dan sumber bukti',icon=':material/fact_check:'):
                        st.write('Fitur final, urutan/satuan, preprocessing, threshold, versi dependensi, tanggal pelatihan dan kalibrasi belum dapat diverifikasi. Nama fitur pada referensi desain UI tidak dianggap fitur eksperimen.')
                        st.write('Definisi target berasal dari PRD.md dan aturan historis SQLRESULT: realisasi/jatuh tempo/selesai valid; jatuh tempo atau selesai tidak boleh mendahului realisasi. Penerapan target pada eksperimen belum dapat diperiksa tanpa notebook.')
                        if evidence['files']:
                            st.write('Berkas kandidat ditemukan tetapi belum ditelaah. Tidak dimuat atau dijalankan:')
                            st.code('\n'.join(evidence['files'][:20]),language=None)
                        else:st.write('Notebook, artefak model, dan hasil evaluasi belum ditemukan pada lokasi bukti yang diperiksa di workspace. Tidak ada kesimpulan tentang eksperimen di luar workspace ini.')
        if evaluate.open:
            with evaluate,st.container(key='methodology_evaluation_content'):
                with st.container(key='methodology_evaluation',border=True):
                    st.html('<div class="mm-panel-heading"><div><h2 class="mm-evaluation-title">Perbandingan Lima Algoritma</h2><p class="mm-muted">Hasil evaluasi untuk target keterlambatan penyelesaian pembiayaan.</p></div><span class="mm-status">Hasil belum terverifikasi</span></div>')
                    with st.container(key='methodology_evaluation_mode',border=True):
                        choice,hint=st.columns([3,2],vertical_alignment='center')
                        with choice:mode=st.segmented_control('Pilihan Evaluasi',list(EVALUATIONS),default='OOF Training',selection_mode='single',required=True,key='methodology_evaluation_choice')
                        with hint:st.html('<p class="mm-muted">Bandingkan algoritma pada data dan prosedur evaluasi yang sama.</p>')
                    st.html('<p class="mm-mode-help">'+escape(EVALUATIONS[mode])+'</p>'+metrics_html(evidence,mode)+'<p class="mm-muted">Pilihan di atas membuka penjelasan jenis evaluasi. Hasil belum tersedia untuk ketiganya; — bukan 0 atau bukti algoritma belum pernah diuji.</p>')
                with st.container(key='methodology_context',border=True):
                    st.html('<h3>'+icon('settings')+'Konteks Eksperimen</h3><p class="mm-context">Paket fitur: <b>—</b><span>|</span>Jumlah sampel evaluasi: <b>—</b><span>|</span>Versi eksperimen: <b>—</b></p>')
                    with st.expander('Konfigurasi per algoritma',icon=':material/tune:'):
                        st.html(configuration_html())
                        st.caption('Konfigurasi, preprocessing dan penanganan imbalance belum diketahui; tidak mengasumsikan GridSearchCV atau sasaran tuning tertentu.')
                with st.container(key='methodology_metrics',border=True):
                    st.html('<h3>'+icon('book')+'Penjelasan Metrik</h3><p class="mm-success">Precision, recall dan F1-score merujuk kelas terlambat (kelas 1 dalam definisi proyek).</p>')
                    with st.expander('Cara membaca metrik',icon=':material/menu_book:'):
                        st.write('Accuracy: proporsi seluruh prediksi benar. Precision: proporsi benar-benar terlambat dari prediksi terlambat. Recall: proporsi terlambat yang terdeteksi. F1-score: rata-rata harmonik precision dan recall.')
                        st.write('ROC-AUC memakai skor kontinu untuk membedakan kelas pada berbagai threshold; bukan bukti kalibrasi probabilitas. Nilai dari konfigurasi berbeda tidak digabung menjadi satu baris terbaik.')
                with st.container(key='methodology_caveats',border=True):
                    st.html('<p class="mm-warning">Hasil eksperimen belum dapat diverifikasi; performa dan kepatuhan prosedur belum dapat dinilai.</p>')
                    with st.expander('Prosedur dan keterbatasan',icon=':material/shield:'):
                        st.write('Ketentuan proyek: preprocessing dipelajari hanya pada training setiap fold. Seleksi fitur, parameter dan threshold memakai training/OOF. OOF, data uji dan temporal dilaporkan terpisah. Belum ada bukti bahwa protokol tertentu telah diterapkan dalam eksperimen.')
                        st.write('OOF yang berulang kali digunakan untuk seleksi tidak independen. Jika data uji berulang kali digunakan untuk keputusan pengembangan, hasilnya eksploratif. Kesesuaian fitur historis dengan aktif, waktu ketersediaan fitur, jadwal awal, dan input anomali wajib diverifikasi sebelum integrasi.')
                st.html('<p class="mm-readonly">Halaman ini hanya membaca dokumentasi. Tidak menjalankan training, mengubah threshold, atau mengaktifkan skor.</p>')
        if data.open:
            with data,st.container(key='methodology_data_content'):
                with st.container(key='methodology_sources',border=True):
                    st.html('<h2>'+icon('database')+'Data yang Digunakan</h2><p class="mm-muted">Setiap indikator mengikuti sumber, cakupan, dan tanggal data yang sesuai.</p>'+sources_html(report)+'<p class="mm-soft-note">Aktif, historis, dan kamus memiliki peran berbeda. Tidak menjumlahkan kontrak lintas sumber atau menyambungkannya tanpa kunci yang sah.</p>')
                with st.container(key='methodology_definitions',border=True):
                    heading,search=st.columns([3,1],vertical_alignment='center')
                    with heading:st.html('<h2>'+icon('book')+'Arti Indikator Dashboard</h2><p class="mm-muted">Definisi, rumus, dan batas penggunaan metrik analitik.</p>')
                    with search:query=st.text_input('Cari indikator',key='methodology_indicator_search',label_visibility='collapsed',placeholder='Cari indikator…',max_chars=100,icon=':material/search:')
                    definitions=filter_definitions(query)
                    if definitions:st.html(definitions_html(definitions))
                    else:st.info('Tidak ada indikator yang cocok dengan pencarian.')
                with st.container(key='methodology_data_notes'):
                    with st.expander('Memahami tanggal laporan',expanded=True,icon=':material/event:'):
                        position=position_text(report) if report else 'Belum ada publikasi aktif'
                        export=export_text(report) if report else 'Belum tercatat'
                        st.html('<div class="mm-date-grid"><div><strong>Tanggal posisi</strong><p>Tanggal kondisi yang direpresentasikan laporan.</p><small>'+escape(position)+'</small></div><div><strong>Waktu ekspor</strong><p>Waktu file diambil dari aplikasi BMT.</p><small>'+escape(export)+'</small></div><div><strong>Waktu unggah</strong><p>Waktu file masuk ke sistem BI; bukan tanggal posisi.</p></div></div><p class="mm-soft-note">Waktu publikasi berbeda lagi. Tanggal posisi unknown tidak diganti tanggal unggah, realisasi, publikasi atau hari ini.</p><p class="mm-warning">Tanpa posisi terkonfirmasi dan cakupan sebanding, tren posisi dan pengingat 7/14/30 hari tidak tersedia. Pembaruan di aplikasi sumber tidak otomatis muncul di BI.</p>')
                    with st.expander('Bagaimana data diolah?',icon=':material/schema:'):
                        st.write('Ekstraksi sumber asli → pemetaan tipe/kode → validasi dan lineage → kandidat versi → rekonsiliasi → publikasi atomik. Dashboard membaca current_publications, bukan kandidat ready terbaru.')
                        st.write('Rekening dan kode tetap teks. Temuan anomali disimpan; tanggal tidak valid menjadi NULL untuk analisis terkait. Saldo valid tetap masuk KPI nominal. Transaksi belum menjadi snapshot posisi atau fitur historis otomatis.')
                    with st.expander('Ketentuan membaca hasil',icon=':material/rule:'):
                        st.write('NPF <5% tidak otomatis membuktikan BMT sehat/aman. Rasio gabungan berasal dari total pembilang/penyebut, bukan rata-rata rasio kelompok. Data kosong, penyebut nol, dan kategori tidak diketahui diberi status; bukan ditebak 0%.')
                        st.write('Perlu Ditinjau = tunggakan pokok >0 ATAU KL/D/M, satu kontrak sekali walaupun memenuhi keduanya. Ukuran portofolio bukan ukuran kualitas atau penilaian pribadi marketing.')
                        st.write('Simulasi membagi outstanding pokok ke jumlah bulan positif. Tanggal input adalah pembayaran pertama, bukan posisi laporan. Pembayaran reguler dibulatkan turun ke Rp0,01; sisa pada pembayaran terakhir menjaga total tepat. Tidak mencakup margin, denda, biaya atau penghematan akad lama, serta tidak mengubah KPI, kontrak, kolektibilitas atau skor.')
        st.html('<p class="mm-footer">Dokumentasi model dan metodologi mendukung transparansi analisis bagi pengambilan keputusan pimpinan.</p>')
