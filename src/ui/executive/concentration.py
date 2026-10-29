"""Concentration components following the paired referensi desain UI."""
from collections import Counter
from html import escape
import streamlit as st
from src.auth.ui import page_guard
from src.ui.shared.paths import ROOT
from src.ui.executive.layout import FILTER_KEYS, dimension_filter, reset_filters
from src.ui.shared.formatters import number, rupiah, compact_rupiah, percent
from src.ui.executive.treemap import treemap_rectangles
from src.ui.executive.motion import percent_markup,scope_attributes

GROUPS={'sector':'Sektor','marketing':'Marketing'}
METRICS={'outstanding':'Outstanding','contracts':'Jumlah Kontrak'}
COLORS=('#2d5a1e','#1f6f68','#4a6b82','#738b6d','#52796f','#7b744b','#426a7c','#597d54')
NPF_REASONS={'unknown_collectibility':'NPF belum lengkap: kolektibilitas tidak dikenali.',
             'zero_outstanding':'NPF tidak tersedia: outstanding nol.',
             'empty_selection':'Tidak ada kontrak pada cakupan ini.'}
_VIEW=st.components.v2.component('concentration_view',html='<div class="cn-host"></div>',
                               js=(ROOT/'assets/js/concentration.js').read_text(encoding='utf-8'),isolate_styles=False)


def initialize():
    st.session_state.setdefault('concentration_group','sector')
    st.session_state.setdefault('concentration_metric','outstanding')


def reset_concentration():
    reset_filters()
    st.session_state['concentration_group']='sector'
    st.session_state['concentration_metric']='outstanding'


def controls(context):
    with st.container(key='concentration_filters',border=True):
        marketing,sector,group,reset=st.columns([1,1,1.5,.6],vertical_alignment='center')
        with marketing:dimension_filter('Marketing',context['marketing'],FILTER_KEYS[0])
        with sector:dimension_filter('Sektor',context['sectors'],FILTER_KEYS[1])
        with group:st.selectbox('Kelompokkan berdasarkan',list(GROUPS),format_func=GROUPS.get,key='concentration_group')
        with reset:st.button('Reset filter',on_click=reset_concentration,icon=':material/restart_alt:')


def _metric_changed():
    value=st.session_state['concentration_view'].metric
    if value in METRICS:st.session_state['concentration_metric']=value


def _open_group():
    from src.ui.executive.monitoring import open_group_monitoring
    if not open_group_monitoring(st.session_state['concentration_view'].open,st.session_state.get('_concentration_scope',{})):
        st.session_state['_concentration_message']='Kelompok tidak lagi tersedia. Pilih ulang dari tampilan terbaru.'


def concentration_html(result):
    metric=result['metric'];key='outstanding_principal' if metric=='outstanding' else 'active_contracts'
    measure='outstanding' if metric=='outstanding' else 'kontrak'
    groups=result['groups'];total=result['totals']
    duplicated=Counter(row['label'] for row in groups)
    labels={row['id']:(row['label'] or 'Belum terpetakan')+(f' · #{row["id"]}' if duplicated[row['label']]>1 else '')+
            (' · belum terpetakan' if row['label'] and row['mapping_status']!='mapped' else '') for row in groups}
    canonical=sorted(groups,key=lambda row:(-row['kpis']['outstanding_principal'],row['id']))
    colors={row['id']:(COLORS[i%len(COLORS)] if row['mapping_status']=='mapped' else '#64748b') for i,row in enumerate(canonical)}
    largest=[g for g in groups if g['id'] in result['largest']]
    if largest:
        names=' / '.join(labels[g['id']] for g in largest)
        value=largest[0]['kpis'][key]
        subtitle=(compact_rupiah(value)+' dari total '+compact_rupiah(total[key])) if metric=='outstanding' else f'{number(value)} dari {number(total[key])} kontrak'
        largest_label='outstanding' if metric=='outstanding' else 'jumlah kontrak'
        hero=f'<div><span class="cn-eyebrow">Kelompok dengan {largest_label} terbesar</span><h2>{escape(names)}</h2><p>{escape(subtitle)}</p></div><div class="cn-share"><strong>{percent_markup(largest[0]["share_percent"],percent(largest[0]["share_percent"]))}</strong><span>porsi {measure}</span><p>{number(total["active_contracts"])} kontrak dalam cakupan data</p></div>'
    else:
        hero='<div><span class="cn-eyebrow">Kelompok terbesar</span><h2>Belum dapat ditentukan</h2><p>Porsi memerlukan total positif dan bobot yang valid.</p></div>'
    tiles=[]
    if result['metric_available']:
        by_id={g['id']:g for g in groups}
        rectangles=treemap_rectangles([(g['id'],g['kpis'][key]) for g in groups])
        for rect in rectangles:
            row=by_id[rect['id']];identifier=row['id'];name=labels[identifier]
            tooltip=f'{name}: {number(row["kpis"]["active_contracts"])} kontrak; {rupiah(row["kpis"]["outstanding_principal"])} outstanding; porsi {measure} {percent(row["share_percent"])}'
            geometry=';'.join(f'{prop}:{rect[field]*100}%' for prop,field in (('left','x'),('top','y'),('width','width'),('height','height')))
            tiles.append(f'<button type="button" class="cn-tile" data-pick="{identifier}" data-weight="{row["kpis"][key]}" aria-pressed="false" aria-label="{escape(tooltip)}" title="{escape(tooltip)}" style="{geometry};background:{colors[identifier]}"><span class="cn-tile-name">{escape(name)}</span><span class="cn-tile-info">{escape(compact_rupiah(row["kpis"]["outstanding_principal"]))} · {number(row["kpis"]["active_contracts"])} kontrak</span><strong>{percent(row["share_percent"])}</strong><small>porsi {measure}</small></button>')
    legends=[];body=[]
    for row in groups:
        identifier=row['id'];name=labels[identifier];k=row['kpis']
        dot=f'<i style="background:{colors[identifier]}" aria-hidden="true"></i>'
        legend_value=compact_rupiah(k['outstanding_principal']) if metric=='outstanding' else number(k['active_contracts'])+' kontrak'
        legends.append(f'<button type="button" class="cn-legend-item" data-pick="{identifier}" aria-pressed="false">{dot}<span><strong>{escape(name)}</strong><small>{escape(legend_value)} · {percent(row["share_percent"])} {measure}</small></span></button>')
        values=(dot+escape(name),number(k['active_contracts']),f'<span title="{rupiah(k["outstanding_principal"])}">{compact_rupiah(k["outstanding_principal"])}</span>',
                percent(row['share_percent']),compact_rupiah(k['overdue_principal']),compact_rupiah(k['npf_outstanding']),
                f'<span title="{escape(NPF_REASONS.get(row["npf_reason"], "Outstanding KL/D/M kelompok ÷ outstanding kelompok × 100%"))}">{percent(k["npf_percent"])}</span>',
                f'<button type="button" data-open="{identifier}">Lihat Pembiayaan →</button>')
        body.append(f'<tr data-group="{identifier}">'+''.join('<td>'+str(value)+'</td>' for value in values)+'</tr>')
    if not body:body=['<tr><td colspan="8">Tidak ada kontrak dalam cakupan filter ini.</td></tr>']
    headings=('Kelompok','Jumlah Kontrak','Outstanding','Porsi '+('Outstanding' if metric=='outstanding' else 'Kontrak'),'Tunggakan Pokok','Outstanding KL, D, M','NPF Kelompok','Aksi')
    switches=''.join(f'<button type="button" data-metric="{m}" aria-pressed="{str(metric==m).lower()}">{label}</button>' for m,label in METRICS.items())
    available=bool(tiles)
    chart=''.join(tiles) if available else '<div class="cn-no-chart">Porsi '+measure+' belum tersedia untuk digambar.</div>'
    return f'''<div class="cn-root" {scope_attributes(result,'Konsentrasi Portofolio')} data-metric="{metric}"><section class="cn-hero">{hero}</section>
<section class="cn-panel cn-distribution"><header><div><h2>Sebaran Pembiayaan per {GROUPS[result['group_by']]}</h2><p>Luas bidang menunjukkan porsi {measure} dalam cakupan data. Peringkat mengikuti ukuran yang dipilih.</p></div><div class="cn-switch" role="group" aria-label="Ukuran treemap">{switches}</div></header>
<button type="button" class="cn-clear" hidden>Hapus sorotan</button><div class="cn-treemap" aria-label="Treemap {measure}">{chart}</div><div class="cn-legend">{''.join(legends)}</div>
<footer><span>Total {number(total['active_contracts'])} kontrak dan {rupiah(total['outstanding_principal'])} saldo pokok. Luas bidang proporsional.</span><span>Klik kelompok untuk menyorot rincian pada tabel.</span></footer></section>
<section class="cn-panel cn-details"><header><div><h2>Rincian Konsentrasi dan Kualitas</h2><p>Porsi {measure}, tunggakan pokok, dan NPF masing-masing kelompok.</p></div></header>
<div class="cn-table-scroll" tabindex="0" role="region" aria-label="Rincian Konsentrasi dan Kualitas"><table><thead><tr>{''.join('<th scope="col">'+h+'</th>' for h in headings)}</tr></thead><tbody>{''.join(body)}</tbody><tfoot><tr><th>Total</th><td>{number(total['active_contracts'])}</td><td>{compact_rupiah(total['outstanding_principal'])}</td><td>{'100,00%' if result['metric_available'] else '—'}</td><td>{compact_rupiah(total['overdue_principal'])}</td><td>{compact_rupiah(total['npf_outstanding'])}</td><td>{percent(total['npf_percent'])}</td><td>—</td></tr></tfoot></table></div>
<footer>Porsi {measure} = {measure} kelompok ÷ total {measure} cakupan. NPF kelompok = outstanding KL/D/M kelompok ÷ outstanding kelompok. NPF total dihitung dari total nominal, bukan rata-rata rasio kelompok.</footer></section>
<footer class="cn-note">ⓘ Pengelompokan bersifat deskriptif. Konsentrasi tidak sama dengan prediksi risiko. Metodologi belum tersedia.</footer></div>'''


def render_concentration(result):
    st.session_state['_concentration_scope']=dict(publication_id=result['publication']['publication_id'],
        group_by=result['group_by'],**result['filters'],ids=[g['id'] for g in result['groups']])
    _VIEW(data={'html':concentration_html(result)},key='concentration_view',on_metric_change=_metric_changed,on_open_change=_open_group)
