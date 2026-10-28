from src.ui.assets import asset_text
"""Quality presentation reconstructed from the paired referensi desain UI.

Trusted local script only; all dynamic content is escaped. Interactions highlight
the current snapshot in the browser and never query or mutate the database.
"""
from decimal import Decimal
from html import escape
import streamlit as st

from src.database.portfolio_quality import quality_summary
from src.ui.motion import percent_markup,scope_attributes
from src.ui.executive import ROOT, CATEGORIES, number, rupiah, compact_rupiah, percent


def _money(value):
    return f'<span title="{escape(rupiah(value))}">{escape(compact_rupiah(value))}</span>'


def quality_html(result):
    k = result['kpis']
    summary = quality_summary(result)
    rows = [row for row in result['composition'] if row['code'] != 'UNKNOWN' or row['contracts']]
    legend, details, bars = [], [], []
    for row in rows:
        code = row['code']
        label, color = CATEGORIES[code]
        dot = f'<i class="qp-dot" style="background:{color}" aria-hidden="true"></i>'
        tooltip = f'{label}: {number(row["contracts"])} kontrak; outstanding {rupiah(row["outstanding_principal"])}'
        legend.append(f'<tr data-category="{code}" class="qp-legend-row"><td><button type="button" data-pick="{code}" aria-pressed="false" title="Sorot {label}">{dot}{label}</button></td><td>{percent(row["contract_share_percent"])} <small>({number(row["contracts"])} kontrak)</small></td><td>{percent(row["outstanding_share_percent"])} <small>({_money(row["outstanding_principal"])})</small></td></tr>')
        details.append(f'<tr data-category="{code}" class="qp-detail-row"><th scope="row">{dot}{label}</th><td>{number(row["contracts"])}</td><td>{_money(row["outstanding_principal"])}</td><td class="qp-overdue">{_money(row["overdue_principal"])}</td><td><span>Melalui Pemantauan</span></td></tr>')
    for key, label, total, available in (
        ('contract_share_percent', 'Jumlah Kontrak', number(k['active_contracts']), result['availability']['contract_shares']),
        ('outstanding_share_percent', 'Outstanding', compact_rupiah(k['outstanding_principal']), result['availability']['outstanding_shares']),
    ):
        normal = next(row[key] for row in rows if row['code'] == 'L')
        context = f'Lancar {percent(normal)} · KL, D, M {percent(summary["npf_shares"][key])}'
        if result['unknown_collectibility_contracts']:
            context += ' · Ada kategori tidak dikenali'
        segments = []
        if available:
            for row in rows:
                share = row[key] or Decimal(0)
                if share <= 0:
                    continue
                code = row['code']
                name, color = CATEGORIES[code]
                width = max(Decimal(0), min(Decimal(100), share))
                tooltip = f'{name}: {number(row["contracts"])} kontrak ({percent(row["contract_share_percent"])}); outstanding {rupiah(row["outstanding_principal"])} ({percent(row["outstanding_share_percent"])})'
                segments.append(f'<button type="button" data-pick="{code}" data-category="{code}" aria-pressed="false" aria-label="{escape(tooltip)}" title="{escape(tooltip)}" style="flex-grow:{width};background:{color}"></button>')
        bars.append(f'<div class="qp-bar-block"><div class="qp-bar-label"><strong>{label} (Total {escape(total)})</strong><span>{escape(context)}</span></div><div class="qp-stacked" aria-label="Komposisi {label}">{"".join(segments) if available else "<span>Porsi tidak tersedia</span>"}</div></div>')
    leading = summary['leading_codes']
    if leading:
        names = ', '.join(CATEGORIES[code][0] for code in leading)
        phrase = 'Kategori dengan outstanding KL, D, M terbesar: ' + names + '.'
        if len(leading) == 1:
            phrase += f' {compact_rupiah(summary["leading_outstanding"])} dari {compact_rupiah(k["npf_outstanding"])}.'
    else:
        phrase = 'Tidak ada outstanding KL, D, M positif dalam cakupan ini.'
    if summary['partial']:
        phrase += ' Ringkasan kategori dikenal; NPF belum lengkap.'
    return f'''<div class="qp-root" {scope_attributes(result,'Kualitas Portofolio')}>
<section class="qp-main-grid">
<article class="qp-panel qp-npf" aria-label="Rasio NPF">
<div><div class="qp-eyebrow">RASIO NPF <span tabindex="0" title="Outstanding KL+D+M dibagi total outstanding cakupan × 100%." aria-label="Rumus NPF: outstanding KL, D, M dibagi total outstanding kali 100 persen">ⓘ</span></div>
<div class="qp-npf-value">{percent_markup(k['npf_percent'],percent(k['npf_percent']))}</div><p>Porsi outstanding KL, D, dan M terhadap total saldo pokok pembiayaan aktif.</p>
<dl><div><dt>Outstanding KL, D, M</dt><dd>{_money(k['npf_outstanding'])}</dd></div><div><dt>Total outstanding</dt><dd>{_money(k['outstanding_principal'])}</dd></div><div><dt>Kontrak KL, D, M</dt><dd>{number(result['npf_contracts'])} dari {number(k['active_contracts'])} kontrak</dd></div><div><dt>Kontrak menunggak</dt><dd>{number(k['contracts_with_arrears'])} kontrak</dd></div></dl></div>
<div class="qp-reference"><div><span>Acuan analisis: <strong>5%</strong></span><span class="qp-badge">Pembanding</span></div><p>Bukan penetapan kesehatan BMT secara keseluruhan.</p></div></article>
<article class="qp-panel qp-composition" aria-label="Jumlah Kontrak vs Outstanding"><header><div><h2>Jumlah Kontrak vs Outstanding</h2><p>Lihat perbedaan porsi kolektibilitas menurut jumlah dan nominal.</p></div><button type="button" class="qp-clear" hidden>Hapus sorotan</button></header>
<div class="qp-bars">{''.join(bars)}</div><div class="qp-table-scroll" tabindex="0" role="region" aria-label="Porsi kolektibilitas"><table class="qp-legend"><thead><tr><th>Kategori</th><th>Porsi Kontrak</th><th>Porsi Outstanding</th></tr></thead><tbody>{''.join(legend)}</tbody></table></div></article>
</section>
<section class="qp-panel qp-details"><header><h2>Rincian per Kolektibilitas</h2><p>Rincian portofolio, porsi pembiayaan, dan tunggakan pokok tertagih.</p></header>
<div class="qp-table-scroll" tabindex="0" role="region" aria-label="Rincian per Kolektibilitas"><table class="qp-detail-table"><thead><tr><th>Kolektibilitas</th><th>Jumlah Kontrak</th><th>Outstanding</th><th>Tunggakan Pokok</th><th>Aksi</th></tr></thead><tbody>{''.join(details)}</tbody><tfoot><tr><th>Total</th><td>{number(k['active_contracts'])}</td><td>{_money(k['outstanding_principal'])}</td><td>{_money(k['overdue_principal'])}</td><td>—</td></tr></tfoot></table></div>
<footer>Catatan: Tunggakan pokok adalah pokok kewajiban tertagih dan bukan merupakan pembilang formula NPF.</footer></section>
<section class="qp-panel qp-finding"><span class="qp-finding-label">TEMUAN UTAMA</span><span>{escape(phrase)}</span></section>
<footer class="qp-note"><span><strong>Catatan:</strong> Kolektibilitas mengikuti data ekspor BMT. Perhitungan menggunakan cakupan data dan filter yang sedang dipilih.</span><span>Metodologi belum tersedia</span></footer>
</div>'''


def render_quality(result):
    st.html('<style>' + asset_text(ROOT/'assets/css/portfolio_quality.css') + '</style>')
    # No database identifiers, raw labels or input values are interpolated in JS.
    st.html(quality_html(result) + '<script>' + asset_text(ROOT/'assets/js/portfolio_quality.js') + '</script>', unsafe_allow_javascript=True)
    st.page_link(ROOT/'pages/executive_monitoring.py',label='Buka Pemantauan & Prioritas',icon=':material/arrow_forward:')
