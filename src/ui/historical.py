"""Historical referensi desain UI, computed from one service result."""
from html import escape
import streamlit as st
from src.ui.executive import number,percent
from src.ui.motion import percent_markup,scope_attributes

KEYS=('historical_year','historical_duration','historical_nominal')


def reset_historical():
    for key in KEYS:st.session_state[key]=None


def analysis_html(result):
    n=result['contracts'];on=result['on_time'];late=result['late']
    cards=''.join(f'<div><span>{label}</span><p><strong>{number(value)}</strong><small>{text}</small></p></div>' for label,value,text in (
        ('Kontrak dianalisis',n,'kontrak'),('Sebelum / tepat jatuh tempo',on,percent_markup(result['on_time_percent'],percent(result['on_time_percent']))+' dari kontrak dianalisis'),
        ('Setelah jatuh tempo',late,percent_markup(result['late_percent'],percent(result['late_percent']))+' dari kontrak dianalisis')))
    maximum=max([b['contracts'] for b in result['delays']]+[1])
    # Visual axis headroom, never changes the computed counts.
    ceiling=max(5,((maximum*6//5+4)//5)*5)
    grid=''.join(f'<div style="bottom:{i*20}%"><span>{number(ceiling*i/5)}</span></div>' for i in range(6))
    bars=''.join(f'<div class="hi-column"><strong>{number(b["contracts"])}</strong><div class="hi-bar" style="height:{b["contracts"]/ceiling*280}px" title="{escape(b["label"])}: {number(b["contracts"])} kontrak ({percent(b["percent"])} dari kontrak terlambat)"></div></div>' for b in result['delays'])
    labels=''.join('<span>'+escape(b['label'])+'</span>' for b in result['delays'])
    def rate(value):return f'<span class="hi-rate">{percent(value)}<i><b style="width:{value or 0}%"></b></i></span>'
    rows=''.join('<tr>'+''.join('<td>'+str(v)+'</td>' for v in (escape(g['label']),number(g['contracts']),number(g['on_time']),number(g['late']),rate(g['late_percent'])))+'</tr>' for g in result['duration_groups'])
    quality=result['quality']
    note=(percent(result['delays'][0]['percent'])+' dari '+number(late)+' kontrak terlambat selesai dalam 1–7 hari setelah jatuh tempo.') if late else 'Tidak ada kontrak terlambat pada tanggal valid dalam cakupan ini.'
    return f'''<div class="hi-root" {scope_attributes(result,'Analisis Historis')}><section class="hi-panel hi-summary"><div class="hi-kpis">{cards}</div><footer>Terlambat: penyelesaian melewati jatuh tempo awal. Dikecualikan dari analisis tanggal: {number(quality['excluded_dates'])} record dalam cakupan.</footer></section>
<section class="hi-panel hi-chart"><h2>Durasi Keterlambatan Penyelesaian</h2><p>Distribusi {number(late)} kontrak yang selesai setelah jatuh tempo.</p><div class="hi-plot"><span class="hi-y-title">Jumlah kontrak</span><div class="hi-grid">{grid}</div><div class="hi-columns">{bars}</div></div><div class="hi-x-labels">{labels}</div><footer>{escape(note)}</footer></section>
<section class="hi-panel hi-duration"><h2>Pola Penyelesaian Menurut Durasi Kontrak</h2><p>Bandingkan tingkat keterlambatan dengan tetap memperhatikan jumlah kontrak.</p><div class="hi-table-scroll" tabindex="0" role="region" aria-label="Pola penyelesaian menurut durasi"><table><thead><tr><th>Durasi Kontrak</th><th>Jumlah Kontrak</th><th>Sebelum / Tepat Waktu</th><th>Terlambat</th><th>Tingkat Keterlambatan</th></tr></thead><tbody>{rows}</tbody><tfoot><tr><th>Total</th><td>{number(n)}</td><td>{number(on)}</td><td>{number(late)}</td><td>{rate(result['late_percent'])}</td></tr></tfoot></table></div></section></div>'''
