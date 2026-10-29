"""Beranda pilot presentation; values come from the pinned KPI result."""
from decimal import Decimal
from html import escape
import streamlit as st
from src.ui.shared.assets import asset_text
from src.ui.shared.paths import ASSETS
from src.ui.shared.formatters import number,rupiah,compact_rupiah,percent
from src.ui.executive.layout import CATEGORIES,modern_shell_css
from src.ui.executive.motion import percent_markup,scope_attributes,motion_scope


def load_home_styles():
    st.html('<style>'+modern_shell_css()+asset_text(ASSETS/'css/home_redesign.css')+'</style>')


def number_markup(value,final,*,scale=Decimal(1),prefix='',suffix='',places=2,tag='span'):
    """Browser presentation only; final Decimal-formatted text is authoritative."""
    if value is None:return escape(final)
    if tag not in ('span','data'):raise ValueError('Unsupported presentation element')
    return (f'<{tag} data-bmt-count="{escape(str(Decimal(value)/scale))}" '
            f'data-bmt-final="{escape(final,quote=True)}" data-bmt-places="{places}" '
            f'data-bmt-prefix="{escape(prefix,quote=True)}" data-bmt-suffix="{escape(suffix,quote=True)}">'
            f'<span class="bmt-motion-sr">{escape(final)}</span>'
            f'<{tag} aria-hidden="true">{escape(final)}</{tag}></{tag}>')


def amount_markup(value,*,tag='span'):
    final=compact_rupiah(value)
    if value is None:return escape(final)
    for scale,label in ((Decimal('1000000000000'),'triliun'),(Decimal('1000000000'),'miliar'),(Decimal('1000000'),'juta')):
        if abs(value)>=scale:return number_markup(value,final,scale=scale,prefix='Rp',suffix=' '+label,tag=tag)
    return number_markup(value,final,prefix='Rp',tag=tag)


def home_scope(result):
    # Context excludes the view metric: distinguish data refresh from metric-only reruns.
    context=motion_scope(dict(result,metric=None))
    return scope_attributes(result,'Beranda')+' data-bmt-motion="home" data-bmt-context="'+context+'"'


def home_header(principal,result):
    p=result['publication']
    position='Belum ada publikasi' if not p else ('Tanggal posisi belum dikonfirmasi' if p['position_date'] is None or p['position_date_status']!='confirmed' else 'Tanggal posisi: '+p['position_date'].strftime('%d-%m-%Y'))
    st.html('<header class="home-header"><div><p class="home-eyebrow">PIMPINAN / IKHTISAR PORTOFOLIO</p><h1>Beranda</h1></div>'
            '<div class="home-header-meta"><span class="home-position"><i aria-hidden="true"></i>'+escape(position)+'</span>'
            '<span class="home-user">'+escape(principal.display_name)+'</span></div></header>')


def summary_cards(result):
    k=result['kpis']
    specs=[('Kontrak aktif',number_markup(k['active_contracts'],number(k['active_contracts']),places=0),'Satu kontrak per rekening',number(k['active_contracts'])),
           ('Outstanding pokok',amount_markup(k['outstanding_principal']),'Saldo pokok dalam cakupan',rupiah(k['outstanding_principal'])),
           ('Tunggakan pokok',amount_markup(k['overdue_principal']),f'{number(k["contracts_with_arrears"])} kontrak menunggak',rupiah(k['overdue_principal'])),
           ('Rasio NPF',percent_markup(k['npf_percent'],percent(k['npf_percent'])),f'{number(result["npf_contracts"])} kontrak KL, D, M','Outstanding KL+D+M: '+rupiah(k['npf_outstanding']))]
    cards=''.join('<article class="bmt-kpi home-kpi"><span class="home-kpi-label">'+label+'</span><strong class="bmt-kpi-value" title="'+escape(full,quote=True)+'">'+value+'</strong><p>'+escape(note)+'</p></article>' for label,value,note,full in specs)
    st.html('<section '+home_scope(result)+' class="home-kpis" aria-label="Ringkasan portofolio">'+cards+'</section>')


def composition_rows(result):
    return [{'Kategori': CATEGORIES[row['code']][0], 'Jumlah kontrak': row['contracts'], 'Outstanding': rupiah(row['outstanding_principal']), 'Persentase outstanding': percent(row['outstanding_share_percent'])} for row in result['composition'] if row['code'] != 'UNKNOWN' or row['contracts']]


def composition_chart(result,basis='Outstanding'):
    items=[]
    for row in result['composition']:
        if row['code']=='UNKNOWN' and not row['contracts']:continue
        label,color=CATEGORIES[row['code']]
        share=row['outstanding_share_percent'] if basis=='Outstanding' else row['contract_share_percent']
        value=compact_rupiah(row['outstanding_principal']) if basis=='Outstanding' else number(row['contracts'])+' kontrak'
        text=f'{label}: {number(row["contracts"])} kontrak · {rupiah(row["outstanding_principal"])} · {percent(share)} dari cakupan'
        bar='' if share is None else f'<div class="home-bar" data-bmt-home-bar style="height:{max(Decimal(0),min(Decimal(100),share))}%;--category:{color}"></div>'
        items.append(f'<div class="home-column" tabindex="0" aria-label="{escape(text,quote=True)}"><div class="home-bar-space">{bar}<div class="home-chart-tip" role="tooltip">{escape(text)}</div></div><div class="home-column-label"><i style="background:{color}"></i>{escape(label)}</div><strong>{escape(value)}</strong><small>{percent(share)}</small></div>')
    unavailable=all(r['outstanding_share_percent'] is None for r in result['composition']) if basis=='Outstanding' else all(r['contract_share_percent'] is None for r in result['composition'])
    note=('Persentase outstanding tidak tersedia' if basis=='Outstanding' else 'Persentase jumlah kontrak tidak tersedia') if unavailable else 'Porsi terhadap total '+('outstanding' if basis=='Outstanding' else 'kontrak')+' dalam filter yang sama.'
    # <data> inherits the existing total-value typography; the label's span rule
    # must not shrink the new counter. No stylesheet/layout change is required.
    value=amount_markup(result['kpis']['outstanding_principal'],tag='data') if basis=='Outstanding' else number_markup(result['kpis']['active_contracts'],number(result['kpis']['active_contracts'])+' kontrak',suffix=' kontrak',places=0,tag='data')
    st.html('<div '+home_scope(dict(result,metric=basis))+' class="bmt-composition home-plot">'
            '<div class="home-plot-total"><span>Total '+('outstanding pokok' if basis=='Outstanding' else 'kontrak aktif')+'</span><strong>'+value+'</strong></div>'
            '<div class="home-plot-area"><div class="home-gridlines" aria-hidden="true"><span>100%</span><span>75%</span><span>50%</span><span>25%</span><span>0%</span></div><div class="home-columns">'+''.join(items)+'</div></div>'
            '<p class="home-chart-note">'+note+'</p></div>')


def category_panel(result):
    rows=[r for r in result['composition'] if r['code']!='UNKNOWN' or r['contracts']]
    segments=[];details=[]
    for row in rows:
        label,color=CATEGORIES[row['code']];share=row['outstanding_share_percent']
        if share is not None:
            segments.append(f'<span style="width:{max(Decimal(0),min(Decimal(100),share))}%;background:{color}" title="{escape(label)}: {percent(share)}"></span>')
        details.append(f'<div class="home-category"><span><i style="background:{color}"></i>{escape(label)}</span><strong>{percent(share)}</strong><small>{number(row["contracts"])} kontrak · {compact_rupiah(row["outstanding_principal"])}</small></div>')
    st.html('<section '+home_scope(result)+' class="home-category-panel"><div class="home-panel-heading"><h2>Rincian kolektibilitas</h2><p>Porsi outstanding dalam cakupan</p></div>'
            '<div class="home-category-total"><strong>'+number(result['kpis']['active_contracts'])+'</strong><span>kontrak aktif</span></div>'
            '<div class="home-stack" '+('data-bmt-home-reveal ' if segments else '')+'role="img" aria-label="Komposisi outstanding menurut kolektibilitas">'+''.join(segments)+'</div>'
            '<div class="home-category-grid">'+''.join(details)+'</div></section>')


def review_table(review):
    body=[]
    for row in review['rows']:
        code=row['collectibility_code'] if row['collectibility_code'] in CATEGORIES else 'UNKNOWN'
        label,_=CATEGORIES[code]
        maturity=row['maturity_date'].strftime('%d-%m-%Y') if row['maturity_date'] else '—'
        body.append('<tr>'+''.join('<td>'+v+'</td>' for v in (escape(row['financing_code']),escape(row['marketing_name'] or 'Tidak diketahui'),f'<span class="bmt-category bmt-category-{code.lower()}">{escape(label)}</span>',rupiah(row['outstanding_principal']),'<span class="bmt-overdue">'+rupiah(row['overdue_principal'])+'</span>',maturity,escape(row['review_reason'])))+'</tr>')
    if not body:body=['<tr><td colspan="7">Tidak ada pembiayaan yang perlu ditinjau dalam cakupan ini.</td></tr>']
    headers=('Kode pembiayaan','Marketing','Kolektibilitas','Outstanding','Tunggakan pokok','Jatuh tempo','Alasan ditinjau')
    st.html('<div class="bmt-table-scroll" tabindex="0" role="region" aria-label="Tabel pembiayaan untuk ditinjau"><table class="bmt-review-table"><thead><tr>'+''.join('<th scope="col">'+h+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join(body)+'</tbody></table></div>'
            '<div class="bmt-table-footer"><span>Kode anonim, bukan nomor rekening. Detail tersedia di Pemantauan.</span><span>Menampilkan '+str(len(review['rows']))+' dari '+number(review['total'])+' kontrak</span></div>')
