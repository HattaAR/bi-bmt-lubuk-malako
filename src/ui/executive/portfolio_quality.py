"""Quality presentation: one authoritative KPI snapshot, no SQL or business formulas.

Referensi desain UI: approved Beranda shell, distinct category donut/arrears.
SVG geometry is presentation only; all shares and NPF come from the service.
"""
from decimal import Decimal
from html import escape
import streamlit as st
from src.ui.shared.assets import asset_text
from src.ui.shared.paths import ROOT
from src.ui.shared.formatters import number,rupiah,compact_rupiah,percent
from src.ui.executive.layout import CATEGORIES,modern_shell_css
from src.ui.executive.motion import percent_markup,scope_attributes,motion_scope


def load_quality_styles():
    st.html('<style>'+modern_shell_css()+asset_text(ROOT/'assets/css/portfolio_quality.css')+'</style>')


def _scope(result,metric=None):
    context=dict(result,metric=None)
    return (scope_attributes(dict(result,metric=metric),'Kualitas Portofolio')+
            ' data-bmt-motion="quality" data-bmt-context="'+motion_scope(context)+'"')


def _money(value):
    return f'<span title="{escape(rupiah(value))}">{escape(compact_rupiah(value))}</span>'


def _total_markup(value,count):
    final=number(value) if count else compact_rupiah(value)
    scale=Decimal(1);suffix='';prefix='' if count else 'Rp'
    if not count:
        for candidate,unit in ((Decimal('1e12'),' triliun'),(Decimal('1e9'),' miliar'),(Decimal('1e6'),' juta')):
            if abs(value)>=candidate:scale=candidate;suffix=unit;break
    return (f'<span data-bmt-count="{Decimal(value)/scale}" data-bmt-final="{escape(final)}" '
            f'data-bmt-prefix="{prefix}" data-bmt-suffix="{suffix}" data-bmt-places="{0 if count else 2}">'
            f'<span class="bmt-motion-sr">{escape(final)}</span><span aria-hidden="true">{escape(final)}</span></span>')


def quality_html(result,metric='Outstanding'):
    if metric not in ('Outstanding','Jumlah Kontrak'):
        raise ValueError('Unsupported composition metric')
    k=result['kpis']
    rows=[r for r in result['composition'] if r['code']!='UNKNOWN' or r['contracts']]
    count=metric=='Jumlah Kontrak'
    field='contracts' if count else 'outstanding_principal'
    share_field='contract_share_percent' if count else 'outstanding_share_percent'
    total=k['active_contracts'] if count else k['outstanding_principal']
    total_text=number(total) if count else compact_rupiah(total)
    exact_total=number(total)+' kontrak' if count else rupiah(total)
    slices=[];legend=[];details=[];bars=[];offset=Decimal(0)
    maximum=max((r['overdue_principal'] for r in rows),default=Decimal(0))
    for row in rows:
        code=row['code'];label,color=CATEGORIES[code]
        dot=f'<i class="qp-dot" style="background:{color}" aria-hidden="true"></i>'
        value=row[field];share=row[share_field]
        value_text=number(value)+' kontrak' if count else rupiah(value)
        tooltip=f'{label}: {value_text} ({percent(share)})'
        attributes=f'data-category="{code}" data-pick="{code}" aria-pressed="false" aria-label="{escape(tooltip)}"'
        if value>0 and share is not None and share>0:
            # SVG circles retain exact final proportions during the common reveal.
            slices.append(f'<span hidden class="qp-slice-source" {attributes} data-color="{color}" data-offset="{offset}" data-value="{value}" data-share="{share}" data-tooltip="{escape(tooltip)}"></span>')
            offset+=share
        legend.append(f'<button type="button" class="qp-legend-row" {attributes} title="{escape(tooltip)}"><span>{dot}{label}</span><strong>{escape(value_text)}</strong><small>{percent(share)}</small></button>')
        details.append(f'<tr class="qp-detail-row" data-category="{code}"><th scope="row">{dot}{label}</th><td>{number(row["contracts"])}</td><td>{rupiah(row["outstanding_principal"])}</td><td>{percent(row["contract_share_percent"])}</td><td>{percent(row["outstanding_share_percent"])}</td><td>{rupiah(row["overdue_principal"])}</td></tr>')
        overdue=row['overdue_principal']
        width=overdue/maximum*100 if maximum>0 else Decimal(0)
        bar=(f'<b data-bmt-quality-bar style="width:{width}%;background:{color}"></b>' if overdue>0 else '')
        tip=f'{label}: tunggakan pokok {rupiah(overdue)}'
        bars.append(f'<div class="qp-arrears-row" data-category="{code}" data-arrears="{overdue}" tabindex="0" title="{escape(tip)}" aria-label="{escape(tip)}"><span class="qp-arrears-label">{dot}{label}</span><span class="qp-arrears-track">{bar}</span><strong>{_money(overdue)}</strong></div>')
    donut=(f'<div class="qp-donut-reveal" data-bmt-quality-donut data-label="Komposisi {metric}">{"".join(slices)}</div>' if slices else '')
    unavailable='' if slices else '<p class="qp-empty">Komposisi belum tersedia untuk total nol.</p>'
    npf_note={'empty_selection':'Tidak ada kontrak dalam cakupan filter.',
              'zero_outstanding':'NPF tidak tersedia: total outstanding nol.',
              'unknown_collectibility':'NPF belum lengkap: terdapat kolektibilitas tidak dikenali.'}.get(result['npf_reason'],'Outstanding KL+D+M ÷ total outstanding dalam cakupan yang sama.')
    return f'''<div class="qp-root" {_scope(result)}>
<div class="qp-main-grid">
<article class="qp-panel qp-npf" {_scope(result)} aria-label="Rasio NPF">
<div class="qp-eyebrow">RASIO NPF</div><div class="qp-npf-value">{percent_markup(k['npf_percent'],percent(k['npf_percent']))}</div>
<p class="qp-formula">{escape(npf_note)}</p>
<dl class="qp-npf-context"><div><dt>Outstanding KL+D+M</dt><dd>{_money(k['npf_outstanding'])}</dd></div><div><dt>Total outstanding</dt><dd>{_money(k['outstanding_principal'])}</dd></div></dl>
<div class="qp-contracts"><div><strong>{number(result['npf_contracts'])}</strong><span>kontrak KL+D+M</span></div><div><strong>{number(k['contracts_with_arrears'])}</strong><span>kontrak menunggak</span></div></div>
</article>
<article class="qp-panel qp-composition" {_scope(result,metric)} aria-label="Komposisi kolektibilitas">
<header><div><h2>Komposisi kolektibilitas</h2><p>{escape(metric)} dalam cakupan filter yang sama.</p></div><button class="qp-clear" type="button" hidden>Hapus sorotan</button></header>
<div class="qp-donut-layout"><div class="qp-donut"><div class="qp-donut-track" aria-hidden="true"></div>{donut}<div class="qp-donut-total" title="{escape(exact_total)}"><strong>{_total_markup(total,count)}</strong><span>{'kontrak aktif' if count else 'outstanding pokok'}</span></div></div><div class="qp-legend">{''.join(legend)}</div></div>{unavailable}
<footer>Sorot kategori untuk melihat rinciannya. Sorotan tidak mengubah filter.</footer>
</article></div>
<section class="qp-panel qp-arrears" {_scope(result)} aria-label="Tunggakan pokok per kolektibilitas"><header><div><h2>Tunggakan pokok per kolektibilitas</h2><p>Pokok tertunggak, berbeda dari outstanding KL+D+M.</p></div><div class="qp-section-total"><span>Total tunggakan</span><strong>{_money(k['overdue_principal'])}</strong></div></header>
<div class="qp-arrears-chart">{''.join(bars)}<div class="qp-axis"><span>Rp0</span><span>{compact_rupiah(maximum/2)}</span><span>{compact_rupiah(maximum)}</span></div></div></section>
<section class="qp-panel qp-details"><header><div><h2>Rincian per kolektibilitas</h2><p>Nilai lengkap dalam satu publikasi dan cakupan filter.</p></div></header>
<div class="qp-table-scroll" tabindex="0" role="region" aria-label="Rincian per kolektibilitas"><table class="qp-detail-table"><thead><tr><th>Kolektibilitas</th><th>Jumlah kontrak</th><th>Outstanding</th><th>Porsi kontrak</th><th>Porsi outstanding</th><th>Tunggakan pokok</th></tr></thead><tbody>{''.join(details)}</tbody><tfoot><tr><th>Total</th><td>{number(k['active_contracts'])}</td><td>{rupiah(k['outstanding_principal'])}</td><td>{percent(Decimal(100) if k['active_contracts'] else None)}</td><td>{percent(Decimal(100) if k['outstanding_principal'] else None)}</td><td>{rupiah(k['overdue_principal'])}</td></tr></tfoot></table></div>
<footer>Tunggakan pokok merupakan bagian dari outstanding; tidak ditambahkan kembali dan bukan pembilang NPF.</footer></section></div>'''


def _retain_metric():
    """A single composition always has a selected, explicitly labelled unit."""
    key='quality_composition_basis'
    selected=st.session_state.get(key) or st.session_state.get('quality_composition_last','Outstanding')
    st.session_state[key]=selected
    st.session_state['quality_composition_last']=selected


def render_quality(result):
    if st.session_state.get('quality_composition_basis') is None:
        _retain_metric()
    with st.container(key='quality_metric',horizontal=True,vertical_alignment='center'):
        st.caption('UKURAN KOMPOSISI')
        metric=st.segmented_control('Ukuran komposisi kolektibilitas',['Jumlah Kontrak','Outstanding'],
                    default=None,key='quality_composition_basis',label_visibility='collapsed',selection_mode='single',on_change=_retain_metric)
    st.html(quality_html(result,metric or 'Outstanding')+'<script>'+asset_text(ROOT/'assets/js/portfolio_quality.js')+'</script>',unsafe_allow_javascript=True)
    st.page_link(ROOT/'pages/executive/monitoring.py',label='Buka Pemantauan & Prioritas',icon=':material/arrow_forward:')
