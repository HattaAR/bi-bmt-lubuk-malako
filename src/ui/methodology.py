"""Presentation aligned with the three Model & Metodologi referensi desain UI."""
from html import escape
from urllib.parse import quote
from src.services.methodology import ALGORITHMS,METRICS,evaluation_rows

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
