"""Documented BI definitions and evidence availability, never a model loader."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ALGORITHMS=('Decision Tree','Random Forest','XGBoost','LightGBM','SVM')
METRICS=('accuracy','precision','recall','f1','roc_auc')
EVALUATIONS={
    'OOF Training':'OOF: setiap prediksi training dibuat oleh model yang dilatih tanpa bagian data tersebut. OOF yang berulang kali dipakai untuk seleksi bukan evaluasi independen.',
    'Data Uji':'Data uji dipisahkan dari pemilihan fitur, parameter dan threshold. Jika berulang kali diperiksa untuk keputusan pengembangan, hasilnya perlu dilaporkan sebagai eksploratif.',
    'Uji Temporal':'Uji temporal memisahkan data menurut urutan waktu. Hasilnya dilaporkan terpisah dari OOF dan data uji acak; prosedur aktual memerlukan bukti eksperimen.',
}
# Textual definitions of implemented services; no second implementation of KPI math.
DEFINITIONS=(
    ('Kontrak aktif','Jumlah kontrak pembiayaan dalam satu publikasi dan filter terpilih.','Satu rekening per versi aktif; bukan jumlah transaksi atau nasabah unik.'),
    ('Outstanding pokok','Total sisa pokok pembiayaan dalam laporan dan filter terpilih.','Saldo pokok dalam cakupan yang sama; tidak dijumlahkan lintas posisi.'),
    ('Tunggakan pokok','Total tunggakan_pokok; jumlah kontrak menunggak menghitung nilai > 0.','Bagian dari outstanding, tidak ditambahkan lagi. Kontrak menunggak berbeda dari kontrak KL/D/M.'),
    ('Kolektibilitas','Kategori sumber L, KL, D, M; nilai lain masuk Tidak dikenali.','Tidak dihitung ulang dari hari terhadap tanggal komputer. Skor model tidak mengubah kategori.'),
    ('NPF','Outstanding KL+D+M ÷ total outstanding cakupan × 100%.','Versi/filter sama. Penyebut marketing adalah outstanding marketing itu; gabungan dari total nominal. Penyebut nol/kategori tak dikenal → tidak tersedia.'),
    ('Tingkat keterlambatan historis','Kontrak selesai setelah jatuh tempo awal ÷ kontrak selesai bertanggal valid dalam cakupan × 100%.','Selesai = tgl_akhir_trans pada SQLRESULT. Tanggal kosong/anomali dikecualikan dan dilaporkan, bukan dianggap tepat waktu.'),
    ('Porsi outstanding','Outstanding kelompok ÷ total outstanding dalam cakupan × 100%.','Ukuran konsentrasi nominal, bukan penilaian risiko atau kinerja marketing. Penyebut nol → tidak tersedia.'),
)


def inspect_evidence(root=ROOT):
    """Inventory names only, even for new/untrusted files. Never execute or load.

    A future verified experiment registry is a separate feature; discovering a
    filename is not verification and cannot enable metrics or scoring.
    """
    root=Path(root).resolve();files=[]
    for directory in ('notebooks','models'):
        folder=root/directory
        if not folder.is_dir() or folder.is_symlink():continue
        for path in sorted(folder.rglob('*')):
            if not path.is_file() or path.is_symlink() or path.name.lower() in {'readme.md','.gitkeep'}:continue
            if '__pycache__' in path.parts or any(p.startswith('.') for p in path.relative_to(folder).parts):continue
            if not path.resolve().is_relative_to(root):continue
            files.append(path.relative_to(root).as_posix())
    return dict(status='unverified' if files else 'not_found',files=files,
                selected_model=None,model_version=None,trained_at=None,features=None,
                preprocessing=None,threshold=None,calibration_status='unverified',scoring_enabled=False)


def evaluation_rows(evidence,mode):
    if mode not in EVALUATIONS:raise ValueError('Jenis evaluasi tidak dikenali.')
    return [dict(algorithm=name,**dict.fromkeys(METRICS)) for name in ALGORITHMS]


def filter_definitions(query=''):
    query=query.strip().casefold()
    return [row for row in DEFINITIONS if query in ' '.join(row).casefold()]
