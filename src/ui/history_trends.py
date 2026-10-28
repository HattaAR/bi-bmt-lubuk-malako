"""Referensi desain UI Riwayat & Tren; honest empty-state and real inventory."""
from html import escape
from urllib.parse import quote
from src.ui.executive import number

REASONS={'no_publication':'Belum ada laporan pembiayaan aktif yang dipublikasikan.',
 'insufficient_confirmed_positions':'Diperlukan minimal dua tanggal posisi terkonfirmasi yang berbeda.',
 'source_identity_missing':'Identitas sumber pembanding belum lengkap.',
 'repeated_source':'Pengulangan sumber yang sama tidak membentuk periode posisi baru.',
 'definitions_unverified':'Versi definisi/transformasi berbeda; kesebandingannya belum diverifikasi.',
 'scope_unverified':'Cakupan bisnis antarposisi belum memiliki pengesahan kesebandingan.'}


def decorative_icon(kind):
    """Local SVG image: native st.html sanitizes inline SVG elements."""
    paths={'document':'<rect x="4" y="3" width="16" height="18" rx="1"/><path d="M8 7h8M8 11h8M8 15h5"/>',
           'trend':'<path d="m3 15 5-7 4 4 5-8M15 4h3v3"/><circle cx="16" cy="16" r="4"/><path d="m19 19 3 3"/>'}
    color='#475569' if kind=='document' else '#94a3b8'
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="'+color+'" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'+paths[kind]+'</svg>'
    return '<img alt="" aria-hidden="true" width="24" height="24" src="data:image/svg+xml,'+quote(svg,safe='')+'">'


def export_text(row):
    if row.get('export_date'):return row['export_date'].strftime('%d-%m-%Y')
    return row.get('export_period_text') or 'Belum tercatat'


def position_text(row):
    if row.get('position_date') and row.get('position_date_status')=='confirmed':return row['position_date'].strftime('%d-%m-%Y')
    return ((row['position_date'].strftime('%d-%m-%Y')+' · ') if row.get('position_date') else '')+'Belum dikonfirmasi'


def reports_html(reports,current):
    rows=[]
    for row in reports:
        source=' / '.join(s['filename']+' · '+s['sheet'] for s in row['sources']) or 'Sumber belum tercatat'
        status='Tanggal belum terkonfirmasi' if row['position_date_status']!='confirmed' or row['position_date'] is None else 'Cakupan belum diverifikasi'
        if current and current['publication_id']==row['publication_id']:source+=' · publikasi aktif'
        cells=(f'<code>{escape(source)}</code>',escape(export_text(row)),escape(position_text(row)),
               f'{number(row["contracts"])} kontrak dalam versi; cakupan perbandingan belum disahkan',f'<span class="rt-badge">{status}</span>')
        rows.append('<tr>'+''.join('<td>'+c+'</td>' for c in cells)+'</tr>')
    body=''.join(rows) if rows else '<tr><td colspan="5">Belum ada laporan aktif terpublikasi. Kandidat/unggahan tidak dianggap periode tren.</td></tr>'
    return '<div class="rt-table-scroll" tabindex="0" role="region" aria-label="Laporan posisi tersedia"><table><thead><tr><th>Sumber Data</th><th>Waktu Ekspor</th><th>Tanggal Posisi</th><th>Cakupan</th><th>Status Perbandingan</th></tr></thead><tbody>'+body+'</tbody></table></div><p class="rt-table-note">Waktu ekspor, unggah, dan publikasi adalah metadata peristiwa yang berbeda dari tanggal posisi. Waktu yang belum tercatat tidak ditebak.</p>'


def event_rows(inventory):
    return [{'Versi dataset':r['dataset_version_id'],'Status':r['status'],
             'Sumber aktif':' / '.join(s['filename'] for s in r['sources']) or 'Belum tercatat',
             'Tercatat (UTC)':str(r['created_at']),
             'Unggah sumber (UTC)':' / '.join(str(s['uploaded_at']) for s in r['sources']) or 'Belum tercatat',
             'Publikasi (UTC)':str(r['published_at']) if r['published_at'] else 'Belum dipublikasikan'} for r in inventory]
