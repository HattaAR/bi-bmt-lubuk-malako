"""Native simulation controls and referensi desain UI presentation."""
from html import escape
from datetime import date
import streamlit as st
from src.auth.ui import page_guard
from src.ui.shared.paths import ROOT
from src.ui.shared.formatters import number, rupiah, percent
from src.ui.executive.monitoring import badge
from src.ui.executive.motion import scope_attributes

DEFAULTS=dict(sim_code=None,sim_search='',sim_expected_publication=None,sim_months=12,sim_month_slider=12,sim_start=None,sim_result=None)


def initialize():
    for key,value in DEFAULTS.items():st.session_state.setdefault(key,value)


def invalidate():st.session_state['sim_result']=None


def search_changed():
    invalidate();st.session_state['sim_code']=None;st.session_state['sim_expected_publication']=None


def contract_changed():
    invalidate();st.session_state['sim_expected_publication']=st.session_state.get('_sim_choice_publication')


def months_changed():
    st.session_state['sim_month_slider']=st.session_state['sim_months'];invalidate()


def slider_changed():
    st.session_state['sim_months']=st.session_state['sim_month_slider'];invalidate()


def reset_scenario():
    for key in ('sim_months','sim_month_slider','sim_start','sim_result'):st.session_state[key]=DEFAULTS[key]


def open_from_monitoring(result):
    page_guard('executive')
    for key,value in DEFAULTS.items():st.session_state[key]=value
    st.session_state['sim_code']=result['detail']['financing_code']
    st.session_state['sim_expected_publication']=result['publication']['publication_id']
    st.switch_page(ROOT/'pages/executive/simulation.py')


def contract_html(row):
    values=(('Kode',escape(row['financing_code'])),('Marketing',escape(row['marketing_name'] or 'Belum terpetakan')),
            ('Kolektibilitas',badge(row['collectibility_code'])),('Outstanding Pokok',rupiah(row['outstanding_principal'])),
            ('Tunggakan Pokok',rupiah(row['overdue_principal'])))
    return '<div class="sm-contract">'+''.join('<div><span>'+k+'</span><strong>'+v+'</strong></div>' for k,v in values)+'</div><p class="sm-muted">Tunggakan pokok merupakan bagian outstanding pokok dan tidak dijumlahkan kembali.</p>'


def result_html(result,*,publication=None):
    attributes=scope_attributes({'publication':publication},'Simulasi Jadwal')
    return f'''<section {attributes} class="sm-result"><header><h2>Hasil Skenario</h2><span>Skenario aktif</span></header><div class="sm-estimate"><span>Estimasi Pokok per Bulan</span><p><strong>{rupiah(result['regular_principal'])}</strong><small>/ bulan ({result['months']} periode)</small></p></div><div class="sm-result-grid"><div><span>Pokok Dihitung</span><b>{rupiah(result['principal'])}</b></div><div><span>Jangka Waktu</span><b>{result['months']} bulan</b></div><div><span>Total Pokok Skenario</span><b>{rupiah(result['total_principal'])}</b></div></div><p class="sm-muted">Pembayaran terakhir: {rupiah(result['last_principal'])}. Pertama: {result['start_date']:%d-%m-%Y}.</p><div class="sm-warning">Belum mencakup margin, denda, dan biaya. Hasil merupakan simulasi pembayaran pokok, bukan persetujuan penjadwalan kembali.</div></section>'''


def comparison_html(rows,*,publication=None):
    body=[]
    for row in rows:
        label=' <span class="sm-tag">Skenario Terpilih</span>' if row['selected'] else ''
        body.append(f'<tr data-selected="{str(row["selected"]).lower()}"><td>{row["months"]} bulan{label}</td><td>{rupiah(row["regular_principal"])}</td><td><span class="sm-relative">{percent(row["relative_percent"])}<i><b style="width:{row["relative_percent"] or 0}%"></b></i></span></td><td>{rupiah(row["total_principal"])}</td></tr>')
    attributes=scope_attributes({'publication':publication},'Simulasi Jadwal')
    return '<div '+attributes+' class="sm-table-scroll"><table><thead><tr><th>Jangka Waktu Skenario</th><th>Pokok Reguler per Bulan</th><th>Beban Relatif Bulanan</th><th>Total Pokok</th></tr></thead><tbody>'+''.join(body)+'</tbody></table></div><p class="sm-muted">Beban relatif memakai rata-rata pokok sebelum pembulatan, dibanding alternatif bulanan terbesar pada tabel ini. Bukan penghematan terhadap akad lama. Pembayaran terakhir menyesuaikan sisa pokok.</p>'


def schedule_html(result):
    rows=''.join(f'<tr><td>Bulan ke-{r["period"]}</td><td>{r["date"]:%d-%m-%Y}</td><td>{rupiah(r["principal"])}</td><td>{rupiah(r["balance"])}</td></tr>' for r in result['schedule'])
    return f'<div class="sm-table-scroll sm-schedule"><table><thead><tr><th>Periode</th><th>Tanggal Skenario</th><th>Pembayaran Pokok</th><th>Sisa Pokok</th></tr></thead><tbody>{rows}</tbody><tfoot><tr><th>Total</th><td>—</td><td>{rupiah(result["total_principal"])}</td><td>Rp0,00</td></tr></tfoot></table></div>'
