"""Three real stages; no ETL/publication work merely because a rerun occurs."""
from html import escape
import streamlit as st
from src.auth.admin_actions import validate_upload,load_upload,preview_upload,publish_upload
from src.services.admin_upload import sync_inputs,input_key
from src.ui.admin import layout as ui
from src.ui.shared.formatters import number, rupiah
from src.etl.validate_active import ACTIVE_COLUMNS



def remember_upload():
    file=st.session_state.get('admin_excel')
    draft=st.session_state.setdefault('admin_draft',{})
    draft['upload']=(file.name,file.getvalue()) if file is not None else None


def back(stage):
    st.session_state['admin_workflow']['stage']=stage
    st.session_state['admin_publish_ack']=False


def render():
    flow=st.session_state.setdefault("admin_workflow",dict(stage=1))
    draft=st.session_state.setdefault("admin_draft",{})
    with st.container(key='admin_page'):
        ui.header();ui.stepper(flow['stage'])
        if flow['stage']==1:
            with st.container(key='admin_metadata'):
                ui.section_heading('1. Informasi Laporan & Metadata','tune')
                st.html('<div class="adm-kind-grid"><article class="adm-kind selected"><strong>◉ Pembiayaan Aktif</strong><p>Pemantauan portofolio berjalan, kolektibilitas, NPF, dan pemeriksaan pembiayaan.</p></article><article class="adm-kind"><strong>Pembiayaan Historis Selesai</strong><p>Alur unggah historis pada halaman ini belum tersedia.</p><small>Belum tersedia · gunakan alur historis terpisah</small></article></div>')
                name=st.text_input('Nama Laporan Pengenal *',value=draft.get('report_name',''),max_chars=255,key='admin_report_name',placeholder='Nama laporan pembiayaan aktif')
                st.caption('Nama pengenal untuk versi laporan ini. Tidak menetapkan tanggal posisi.')
                export,position=st.columns(2,gap='medium')
                with export,st.container(key='admin_dates_export'):
                    st.markdown('**Waktu Ekspor dari Aplikasi**')
                    export_unknown=st.checkbox('Waktu ekspor belum diketahui',value=draft.get('export_unknown',True),key='admin_export_unknown')
                    month_col,year_col=st.columns(2)
                    with month_col:
                        months=[None,*range(1,13)];names=('Januari','Februari','Maret','April','Mei','Juni','Juli','Agustus','September','Oktober','November','Desember')
                        month=st.selectbox('Bulan',months,index=months.index(draft.get('export_month')),placeholder='Pilih bulan',format_func=lambda x:'Pilih bulan' if x is None else names[x-1],disabled=export_unknown,key='admin_export_month')
                    with year_col:year=st.number_input('Tahun',min_value=1000,max_value=9999,value=draft.get('export_year'),placeholder='Tahun ekspor',disabled=export_unknown,key='admin_export_year')
                    export_date=st.date_input('Tanggal lengkap (opsional)',value=draft.get('export_date'),disabled=export_unknown,format='DD/MM/YYYY',key='admin_export_date')
                with position,st.container(key='admin_dates_position'):
                    st.markdown('**Tanggal Posisi Data Pembiayaan**')
                    unknown=st.checkbox('Tanggal posisi belum dikonfirmasi / belum diketahui',value=draft.get('position_unknown',True),key='admin_position_unknown')
                    position_date=st.date_input('Tanggal Posisi',value=draft.get('position_date'),disabled=unknown,format='DD/MM/YYYY',key='admin_position_date')
                    st.caption('Tanggal kondisi saldo dan kolektibilitas, dapat berbeda dari waktu ekspor. Isi hanya berdasarkan konfirmasi sumber.')
                scope=st.text_area('Cakupan Laporan',value=draft.get('scope_description',''),height=80,max_chars=2000,key='admin_scope',placeholder='Jelaskan cakupan laporan yang benar-benar diketahui')
            values=dict(report_name=name,scope_description=scope,export_unknown=export_unknown,export_month=month,export_year=year,
                        export_date=export_date,position_unknown=unknown,position_date=position_date)
            draft.update(values)
            with st.container(key='admin_files'):
                ui.section_heading('2. Berkas File Excel','upload',badge='Format .xlsx / .xls')
                st.caption('Unggah ekspor asli. Sheet aktif: SQLRESULT; kamus terkonfigurasi: SQLRESULT1. Maksimal 50 MB.')
                file=st.file_uploader('Pilih File Excel',type=['xls','xlsx'],max_upload_size=50,key='admin_excel',on_change=remember_upload)
                upload=draft.get('upload')
                if file is not None:
                    upload=(file.name,file.getvalue());draft['upload']=upload
                if upload:
                    st.html('<div class="adm-note">'+ui.icon('file')+' '+escape(upload[0])+' · '+number(len(upload[1])/1024,1)+' KB</div>')
                flow=sync_inputs(st.session_state,input_key(upload[0] if upload else '',upload[1] if upload else b'',{k:str(v) if v is not None else None for k,v in values.items()}))
                st.caption('Pemeriksaan tidak memuat kandidat atau menerbitkan data. Salinan sumber disimpan di penyimpanan unggah privat untuk lineage.')
                with st.container(horizontal=True,horizontal_alignment='right'):
                    if st.button('Baca & Periksa File',type='primary',icon=':material/arrow_forward:',disabled=not upload,key='admin_validate'):
                        with st.spinner('Membaca struktur dan memvalidasi sumber…'):ui.call(validate_upload,upload[0],upload[1],values)
                        st.rerun()
            ui.note('Ketentuan integritas: file baru tidak mengganti dashboard secara otomatis. Posisi unknown membatasi tren dan indikator tanggal. Pemuatan kandidat dan publikasi merupakan tindakan admin yang terpisah.')
        elif flow['stage']==2:
            candidate=flow.get('candidate');findings=flow.get('findings',[])
            with st.container(key='admin_file_summary'):
                ui.section_heading(draft.get('upload',('Berkas Excel',))[0],description='Hasil pemeriksaan sumber yang dipilih, tanpa publikasi otomatis.')
                if candidate:ui.file_summary(candidate)
                if st.button('Ubah file atau metadata',icon=':material/arrow_back:',key='admin_edit'):
                    back(1);st.rerun()
            blocking=sum(f.severity=='blocking' for f in findings);warnings=sum(f.severity=='warning' for f in findings)
            with st.container(key='admin_totals'):
                st.html('<div class="adm-stats"><div><small>Baris tervalidasi</small><strong>'+number(candidate.summary['rows'] if candidate else None)+'</strong></div><div class="good"><small>Masalah penghambat</small><strong>'+number(blocking)+'</strong></div><div class="warning"><small>Catatan / warning</small><strong>'+number(warnings)+'</strong></div></div>')
                if candidate:st.caption(f"Rekening unik: {number(candidate.summary['unique_accounts'])}. Nominal awal: {rupiah(candidate.summary['totals']['jml_pinjaman'])}; outstanding: {rupiah(candidate.summary['totals']['saldo_nominatif'])}; tunggakan pokok: {rupiah(candidate.summary['totals']['tunggakan_pokok'])}.")
            with st.container(key='admin_checks'):
                results,preview=st.tabs(['Hasil Pemeriksaan','Pratinjau Data'],key='admin_checks_tab',on_change='rerun')
                if results.open:
                    ui.findings_table(findings,validated=candidate is not None)
                    st.caption('Validasi otomatis tidak menggantikan konfirmasi kebenaran data sumber oleh BMT.')
                if preview.open:
                    if candidate:ui.preview_table(candidate)
                    else:st.info('Pratinjau belum tersedia karena pemeriksaan wajib belum lolos.')
                if warnings:
                    ui.note('Warning tetap disimpan bersama lineage. Tanggal atau atribut anomali tidak menghapus nominal kontrak valid; fungsi yang terdampak dibatasi.')
                    st.checkbox('Saya telah meninjau warning dan memahami batas penggunaan data.',key='admin_warning_ack')
            with st.expander('Pemetaan Kolom & Verifikasi Field Sistem',icon=':material/tune:'):
                st.write('Pemetaan aktif tetap, memakai nama kolom sumber berikut:')
                st.code(', '.join(sorted(ACTIVE_COLUMNS)),language=None)
                st.caption('Marketing/sektor dipetakan melalui kode_group1/2 dari kamus terkonfigurasi. Tidak menggabungkan baris kontrak kedua berkas.')
            back_col,next_col=st.columns([1,2],vertical_alignment='center')
            with back_col:
                if st.button('Kembali ke Tahap 1',key='admin_back_upload'):
                    back(1);st.rerun()
            with next_col,st.container(horizontal=True,horizontal_alignment='right'):
                if 'loaded' not in flow:
                    if st.button('Muat Kandidat',type='primary',disabled=not candidate or blocking>0 or (warnings>0 and not st.session_state.get('admin_warning_ack')),key='admin_load'):
                        with st.spinner('Memuat kandidat dan merekonsiliasi dalam satu transaksi…'):ui.call(load_upload,warnings_acknowledged=st.session_state.get('admin_warning_ack',False))
                        st.rerun()
                else:
                    st.success(f"Kandidat #{flow['loaded'].dataset_version_id} · {flow['loaded'].status}. Rekonsiliasi lulus; belum diterbitkan oleh tindakan ini.")
                    if st.button('Lanjut ke Konfirmasi',type='primary',icon=':material/arrow_forward:',key='admin_preview'):
                        with st.spinner('Memeriksa preview publikasi…'):ui.call(preview_upload)
                        st.rerun()
        else:
            candidate=flow['candidate'];preview=flow['preview']
            st.html('<div><h2 style="margin:0;font-size:20px">Konfirmasi Data untuk Dashboard</h2><p style="margin:4px 0 0;color:#64748b;font-size:14px">Tinjau ringkasan dan dampak penerbitan sebelum melanjutkan.</p></div>')
            if flow.get('published'):
                published=flow['published'];st.success(f"Publikasi #{published['publication_id']} tercatat. "+('Menjadi sumber aktif dashboard.' if published['is_current'] else 'Bukan sumber aktif saat ini; tidak diaktifkan ulang.'))
            with st.container(key='admin_report'):
                ui.section_heading('Ringkasan Laporan','file','Rincian identitas berkas dan kandidat yang akan diaktifkan')
                ui.file_summary(candidate)
                st.caption(f"Kandidat #{preview['candidate']['dataset_version_id']} · status {preview['candidate']['status']} · kamus #{preview['reference']['dataset_version_id'] if preview['reference'] else '—'}")
                if st.button('Ubah',icon=':material/edit:',key='admin_change_report'):
                    back(1);st.rerun()
            with st.container(key='admin_publish_checks'):
                ui.section_heading('Ringkasan Hasil Pemeriksaan','check')
                st.write(f"{len(preview['blockers'])} masalah penghambat · {len(preview['warnings'])} warning tersimpan.")
                if candidate.position_date is None:ui.note('Tanggal posisi belum diketahui. BI statis tersedia; tren posisi dan perhitungan yang memerlukan tanggal posisi belum tersedia.')
                for blocker in preview['blockers']:st.error(blocker['message'])
                if st.button('Lihat hasil pemeriksaan',key='admin_return_checks'):
                    back(2);st.rerun()
            with st.container(key='admin_publish_impact'):
                ui.section_heading('Sumber Data Dashboard','sync','Perbandingan sumber sebelum dan sesudah penerbitan')
                previous=preview['previous_publication'];before=f"Publikasi #{previous['publication_id']} · dataset #{previous['dataset_version_id']}" if previous else 'Belum ada publikasi aktif'
                st.html('<div class="adm-comparison"><article><small>Sumber saat ini (saat preview)</small><strong>'+escape(before)+'</strong><p>Tetap aktif apabila penerbitan dibatalkan atau gagal.</p></article><article><small>Sumber setelah penerbitan</small><strong>'+escape(candidate.report_metadata['report_name'])+'</strong><p>'+number(candidate.summary['rows'])+' kontrak · '+escape(candidate.active_source.path.name)+'</p></article></div>')
                st.caption('Publikasi memperbarui sumber pembiayaan aktif secara atomik. Tidak mengubah aplikasi BMT, data historis, atau konfigurasi model.')
                if st.button('Perbarui preview',icon=':material/refresh:',key='admin_refresh_preview'):
                    with st.spinner('Memeriksa ulang syarat publikasi…'):ui.call(preview_upload)
                    st.rerun()
            if not flow.get('published'):
                st.checkbox('Saya mengonfirmasi kandidat dan dampak publikasi di atas.',key='admin_publish_ack',disabled=not preview['can_publish'])
                left,right=st.columns([1,1],vertical_alignment='center')
                with left:
                    if st.button('Kembali ke Pemeriksaan',key='admin_back_checks'):
                        back(2);st.rerun()
                with right,st.container(horizontal=True,horizontal_alignment='right'):
                    if st.button('Terbitkan ke Dashboard',type='primary',icon=':material/publish:',disabled=not preview['can_publish'] or not st.session_state.get('admin_publish_ack'),key='admin_publish'):
                        with st.spinner('Menerbitkan kandidat secara atomik…'):ui.call(publish_upload,confirmed=st.session_state.get('admin_publish_ack',False))
                        st.rerun()
        ui.footer()
