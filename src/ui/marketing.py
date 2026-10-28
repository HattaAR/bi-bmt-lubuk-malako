"""Portofolio Marketing presentation from the paired referensi desain UI."""
from collections import Counter
from decimal import Decimal,ROUND_CEILING,ROUND_FLOOR,localcontext
from html import escape
import streamlit as st
from src.ui.executive import ROOT,FILTER_KEYS,reset_filters,number,rupiah,compact_rupiah,percent
from src.ui.monitoring import open_group_monitoring
from src.ui.motion import percent_markup,scope_attributes

METRICS={'npf':'Rasio NPF','arrears':'Nominal Tunggakan Pokok'}
REASONS={'unknown_collectibility':'Kolektibilitas tidak dikenali; NPF belum lengkap.',
         'zero_outstanding':'Outstanding nol; NPF tidak tersedia.',
         'empty_selection':'Tidak ada kontrak pada cakupan ini.'}
_VIEW=st.components.v2.component('marketing_view',html='<div class="mk-host"></div>',
    js=(ROOT/'assets/js/marketing.js').read_text(encoding='utf-8'),isolate_styles=False)


def initialize():st.session_state.setdefault('marketing_metric','npf')


def reset_marketing():
    reset_filters();st.session_state['marketing_metric']='npf'


def _metric_changed():
    value=st.session_state['marketing_view'].metric
    if value in METRICS:st.session_state['marketing_metric']=value


def _open_marketing():
    if not open_group_monitoring(st.session_state['marketing_view'].open,st.session_state.get('_marketing_scope',{})):
        st.session_state['_marketing_message']=True


def chart_scale(values):
    """Display axis only; no KPI is calculated here. Retain negative values."""
    values=[Decimal(v) for v in values if v is not None]
    with localcontext() as context:
        context.prec=50
        low=min([Decimal(0),*values]);high=max([Decimal(0),*values])
        if low==high:high=low+1
        raw=(high-low)*Decimal('1.15')/6
        power=Decimal(10)**raw.adjusted()
        step=next(n*power for n in map(Decimal,('1','2','5','10')) if n*power>=raw)
        low=(low/step).to_integral_value(rounding=ROUND_FLOOR)*step
        high=(high*Decimal('1.15')/step).to_integral_value(rounding=ROUND_CEILING)*step if high>0 else Decimal(0)
        return low,high,[low+step*i for i in range(int((high-low)/step)+1)]


def _position(value,low,high):return (Decimal(value)-low)/(high-low)*100


def axis_labels(ticks,metric):
    """One display unit per currency axis, keeping labels compact on laptops."""
    if metric=='npf':return '',[percent(t) for t in ticks]
    magnitude=max(abs(t) for t in ticks)
    scale,unit=next(((s,u) for s,u in ((Decimal('1e12'),'Rp triliun'),(Decimal('1e9'),'Rp miliar'),
                                     (Decimal('1e6'),'Rp juta'),(Decimal('1e3'),'Rp ribu')) if magnitude>=s),(Decimal(1),'Rp'))
    places=max(0,-((ticks[1]-ticks[0])/scale).normalize().adjusted())
    return unit,[number(t/scale,places) for t in ticks]


def marketing_html(result,metric='npf'):
    if metric not in METRICS:raise ValueError('Ukuran grafik tidak tersedia.')
    groups=result['groups'];totals=result['totals'];counts=Counter(g['label'] for g in groups)
    labels={g['id']:(g['label'] or 'Belum terpetakan')+(f' · #{g["id"]}' if counts[g['label']]>1 else '')+
            (' · belum terpetakan' if g['label'] and g['mapping_status']!='mapped' else '') for g in groups}
    field='npf_percent' if metric=='npf' else 'overdue_principal'
    display=percent if metric=='npf' else compact_rupiah
    ordered=sorted(groups,key=lambda g:(g['kpis'][field] is None,-(g['kpis'][field] or 0),labels[g['id']].casefold(),g['id']))
    benchmark=totals['npf_percent'] if metric=='npf' else None
    low,high,ticks=chart_scale([g['kpis'][field] for g in groups]+[benchmark])
    grid=''.join(f'<span style="left:{_position(t,low,high)}%"></span>' for t in ticks)
    axis_unit,tick_labels=axis_labels(ticks,metric)
    axis=''.join(f'<span title="{escape(display(t))}" style="left:{_position(t,low,high)}%">{escape(label)}</span>' for t,label in zip(ticks,tick_labels))
    reference=(f'<div class="mk-reference" style="left:{_position(benchmark,low,high)}%"><span>NPF Gabungan ({percent(benchmark)})</span></div>' if benchmark is not None else '')
    chart=[]
    for g in ordered:
        identifier=g['id'];value=g['kpis'][field];name=labels[identifier]
        reason=REASONS.get(g['npf_reason'],'NPF belum tersedia.') if metric=='npf' else ''
        title=f'{name}: {display(value)}'+(f' · {reason}' if value is None else '')
        if value is None:
            mark=f'<span class="mk-unavailable">— · {escape(reason)}</span>'
        elif metric=='npf':
            mark=f'<span class="mk-point" style="left:{_position(value,low,high)}%"><i></i><strong>{display(value)}</strong></span>'
        else:
            start=min(Decimal(0),value);width=abs(_position(value,low,high)-_position(0,low,high))
            mark=f'<span class="mk-bar" style="left:{_position(start,low,high)}%;width:{width}%"></span><strong class="mk-bar-value" style="left:{_position(max(Decimal(0),value),low,high)}%">{escape(display(value))}</strong>'
        chart.append(f'<button type="button" class="mk-chart-row" data-pick="{identifier}" data-value="{value if value is not None else ""}" aria-pressed="false" title="{escape(title)}"><span class="mk-row-name"><i></i>{escape(name)}</span><span class="mk-track">{mark}</span></button>')
    rows=[]
    for g in sorted(groups,key=lambda g:(labels[g['id']].casefold(),g['id'])):
        k=g['kpis'];identifier=g['id'];reason=REASONS.get(g['npf_reason'],'Outstanding KL/D/M marketing ÷ outstanding marketing × 100%.')
        values=(f'<i></i>{escape(labels[identifier])}',number(k['active_contracts']),
                f'<span title="{rupiah(k["outstanding_principal"])}">{compact_rupiah(k["outstanding_principal"])}</span>',
                f'<span title="{rupiah(k["overdue_principal"])}">{compact_rupiah(k["overdue_principal"])}</span>',
                number(k['contracts_with_arrears']),f'<span title="{rupiah(k["npf_outstanding"])}">{compact_rupiah(k["npf_outstanding"])}</span>',
                f'<span title="{escape(reason)}">{percent(k["npf_percent"])}</span>',
                f'<button type="button" data-open="{identifier}" aria-label="Lihat pembiayaan {escape(labels[identifier])}">Lihat Pembiayaan →</button>')
        rows.append(f'<tr data-marketing="{identifier}">'+''.join('<td>'+str(v)+'</td>' for v in values)+'</tr>')
    empty='<p class="mk-empty">Tidak ada kontrak pada cakupan filter ini.</p>'
    head=('Marketing','Kontrak Aktif','Outstanding','Tunggakan Pokok','Kontrak Menunggak','Outstanding KL, D, M','NPF ⓘ','Aksi')
    heading='Rasio NPF per Marketing' if metric=='npf' else 'Tunggakan Pokok per Marketing'
    subtitle='Grafik titik membandingkan NPF marketing terhadap NPF gabungan cakupan filter.' if metric=='npf' else 'Grafik batang membandingkan nominal tunggakan pokok tercatat per marketing.'
    switches=''.join(f'<button type="button" data-metric="{key}" aria-pressed="{str(metric==key).lower()}">{name}</button>' for key,name in METRICS.items())
    chart_body=f'<div class="mk-plot" style="--mk-rows-height:{max(220,len(groups)*44)}px"><div class="mk-grid">{grid}{reference}</div><div class="mk-rows">{"".join(chart)}</div><div class="mk-axis">{axis}</div>{f"<small class=mk-axis-unit>{axis_unit}</small>" if axis_unit else ""}</div>' if groups else empty
    benchmark_note='<p class="mk-benchmark-note">Garis NPF gabungan tidak tersedia: '+escape(REASONS.get(result['npf_reason'],'NPF belum tersedia.'))+'</p>' if metric=='npf' and benchmark is None and groups else ''
    return f'''<div class="mk-root" {scope_attributes(dict(result,metric=metric),'Portofolio Marketing')} data-metric="{metric}"><section class="mk-summary"><div><i></i><div><strong>{len(groups)} marketing · {number(totals['active_contracts'])} kontrak aktif · {compact_rupiah(totals['outstanding_principal'])} outstanding</strong><p>Perbandingan mempertimbangkan rasio pembiayaan bermasalah, nominal tunggakan, dan ukuran portofolio.</p></div></div><div class="mk-summary-totals"><span>NPF Gabungan: <b>{percent_markup(totals['npf_percent'],percent(totals['npf_percent']))}</b></span><span>Total Tunggakan: <b>{compact_rupiah(totals['overdue_principal'])}</b></span></div></section>
<section class="mk-panel mk-distribution"><header><div><h2>{heading}</h2><p>{subtitle}</p></div><div class="mk-switch" role="group" aria-label="Ukuran perbandingan marketing">{switches}</div></header><button type="button" class="mk-clear" hidden>Hapus sorotan</button>{benchmark_note}{chart_body}<footer><span>Setiap baris merepresentasikan satu marketing. Warna teal bersifat netral, tanpa pelabelan evaluatif.</span><span>Klik baris grafik untuk menyorot rincian pada tabel.</span></footer></section>
<section class="mk-panel mk-details"><header><div><h2>Rincian Portofolio Marketing</h2><p>Jumlah kontrak aktif, outstanding, tunggakan pokok, kontrak menunggak, dan NPF per marketing.</p></div></header><div class="mk-table-scroll" tabindex="0" role="region" aria-label="Rincian Portofolio Marketing"><table><thead><tr>{''.join('<th scope="col">'+h+'</th>' for h in head)}</tr></thead><tbody>{''.join(rows) if rows else '<tr><td colspan="8">Tidak ada kontrak pada cakupan filter ini.</td></tr>'}</tbody><tfoot><tr><th>Total</th><td>{number(totals['active_contracts'])}</td><td>{compact_rupiah(totals['outstanding_principal'])}</td><td>{compact_rupiah(totals['overdue_principal'])}</td><td>{number(totals['contracts_with_arrears'])}</td><td>{compact_rupiah(totals['npf_outstanding'])}</td><td>{percent(totals['npf_percent'])}</td><td>—</td></tr></tfoot></table></div><footer>NPF marketing = outstanding KL/D/M marketing ÷ outstanding marketing × 100%. NPF total dihitung dari total nominal, bukan rata-rata rasio. Kontrak menunggak berarti tunggakan pokok &gt; 0, berbeda dari kontrak KL/D/M.</footer></section>
<footer class="mk-note"><div><strong>ⓘ Catatan Analitik:</strong> Rasio dan nominal memberikan sudut pandang berbeda untuk menentukan kebutuhan peninjauan.<p>Kondisi portofolio perlu ditinjau bersama karakteristik pembiayaan dan pemeriksaan petugas sebelum menilai kinerja marketing.</p></div><span>Metodologi belum tersedia</span></footer></div>'''


def render_marketing(result):
    st.session_state['_marketing_scope']=dict(publication_id=result['publication']['publication_id'],group_by='marketing',
        **result['filters'],ids=[g['id'] for g in result['groups']])
    _VIEW(data={'html':marketing_html(result,st.session_state['marketing_metric'])},key='marketing_view',
          on_metric_change=_metric_changed,on_open_change=_open_marketing)
