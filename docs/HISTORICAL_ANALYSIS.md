# Analisis Historis

Pemeriksaan kesiapan terbaru **3 November 2026**:
[HISTORICAL_READINESS.md](HISTORICAL_READINESS.md). Seluruh 3.709 record tetap
dipertahankan; **BMT sudah mengonfirmasi 44 kelompok bernilai identik merupakan
pembiayaan berbeda**. Audit 45 baris tambahan tetap disimpan tanpa deduplikasi.
Penghitung historis memakai istilah record karena ID kontrak tidak tersedia.
Aturan v3 mencatat konfirmasi sesuai hash/sheet dan menghapus penahanan terkait,
tanpa mengurangi validasi/guard/rekonsiliasi. Record tenor 300 tetap masuk bila
tanggal layak; eksklusi notebook merupakan filter eksperimen tersendiri.
Penerapan berizin berikutnya pada 3 November 2026 menambahkan fakta historis
dan kandidat **53 ready**; rekonsiliasi/preview lulus, belum ada publikasi.
Backup dan bukti aktual: [HISTORICAL_PRODUCTION_CANDIDATE.md](HISTORICAL_PRODUCTION_CANDIDATE.md).

Redesign dan verifikasi terbaru 30 Oktober 2026:
[HISTORICAL_REDESIGN.md](HISTORICAL_REDESIGN.md). Grafik utama kini batang
bertumpuk 100% tepat waktu/terlambat menurut durasi kontrak. Catatan visual
grafik distribusi 1–7/8–30/31–90/>90 di bawah adalah implementasi sebelumnya;
definisi klasifikasi, kelompok dan layanan tetap berlaku.

Referensi desain UI: pasangan `screen.png` dan `code.html` pada
`references/pimpinan/analisis_historis_bi_bmt_lubuk_malako/`. Susunan mengikuti
header, empat kontrol filter, tiga ringkasan, grafik kolom keterlambatan, tabel
durasi, expander kualitas, dan catatan. Inter lokal dan sidebar bersama 256 px
dipertahankan; HTML memakai Plus Jakarta Sans dan sidebar 240 px. Kontrol dan
expander memakai Streamlit native sehingga detailnya berbeda. Tidak ada angka
contoh atau label Data ilustrasi di aplikasi.

## Kesiapan produksi dan prasyarat

Pemeriksaan 25 Oktober 2026: produksi memiliki 14 tabel; belum ada
fact_pembiayaan_historis, versi historical, ataupun current_publications untuk
historical. ETL/publikasi sebelumnya khusus aktif. File lokal SQLRESULT.XLS,
sheet SQLRESULT, memiliki 3.709 record. Dry-run membaca sumber ini sekali tanpa
database: 3.709 tanggal eligible, 2.286 tepat waktu, 1.423 terlambat, nol temuan
tanggal dan nol nominal tidak valid. Hasil ini belum dipublikasikan ke dashboard.

Satu tabel tambahan terbukti diperlukan untuk grain record historis per versi.
Migrasi eksplisit `src.database.historical_schema` membuat tabel InnoDB dengan
FK metadata sumber/versi, kunci unik lineage, indeks versi/tahun, CHECK konsistensi
target/hari, dan tiga trigger perlindungan fakta terpublikasi. Tabel/kolom existing
tidak diubah. Import modul, membuka UI, dry-run, atau load tidak menjalankan DDL.
DDL MySQL auto-commit; penerapan operator adalah langkah terpisah.

Pada pengembangan awal, migrasi/load/publikasi hanya diuji pada database terpisah.
Setelah izin lanjutan 3 November 2026, skema produksi dan load kandidat 53 telah
selesai, sedangkan publikasi tetap belum dilakukan. Halaman `/analisis-historis`
menampilkan belum tersedia selama pointer historis belum ada. Tidak ada
fallback ke aktif, kandidat ready terbaru, MAX(id), atau Excel saat interaksi UI.

## Aturan dan penyebut

- Selesai = tgl_akhir_trans, jatuh tempo awal = tgl_jatuh_tempo pada SQLRESULT.
  Ketiga tanggal realisasi/jatuh tempo/selesai harus bisa diparse; jatuh tempo
  dan selesai tidak boleh mendahului realisasi. Kegagalan menghasilkan target
  NULL dan hari terlambat NULL, bukan tepat waktu.
- Format tanggal memakai parser XLS existing: tanggal Excel dengan datemode
  workbook, dd-Mon-yy/yyyy atau ISO yyyy-mm-dd. Pivot dua digit eksplisit:
  00–68 menjadi 2000–2068; 69–99 menjadi 1969–1999. Tahun tidak diperbaiki dengan
  tebakan. Tidak membandingkan tanggal dengan hari komputer/tanggal posisi aktif.
- Target = 1 bila selesai > jatuh tempo awal, selain itu 0 untuk tanggal eligible.
  Hari terlambat = max(0, selesai − jatuh tempo awal). Durasi kontrak = jatuh
  tempo awal − realisasi, dalam hari; nol hari sah. Durasi tetap dapat disimpan
  bila tanggal selesai tidak valid, tetapi record tidak masuk analisis tanggal.
- KPI: eligible dalam filter. Persentase tepat waktu/terlambat berpenyebut jumlah
  eligible yang sama. Distribusi 1–7, 8–30, 31–90, >90 hanya memuat terlambat;
  persentasenya dibagi jumlah terlambat dalam filter, bukan seluruh kontrak.
- Tabel memakai kelompok ≤90, 91–180, 181–365, >365 hari. Persentase per kelompok
  = terlambat kelompok / eligible kelompok; total dari seluruh eligible, bukan
  rata-rata rasio kelompok. Penyebut nol menghasilkan None/—.
- Periode filter adalah tahun realisasi, bukan tahun penyelesaian. Grafik bukan
  deret waktu. Nominal: < Rp10 juta, Rp10–50 juta termasuk kedua batas, > Rp50 juta,
  mengikuti referensi. Ketiga filter memakai AND untuk seluruh komponen.
- Nominal kosong/negatif/ambigu tidak ditebak nol. Nominal NULL dapat tetap
  mengikuti analisis tanggal tanpa filter nominal; jika filter nominal dipilih,
  kelayakan terhadap filter tidak dapat ditentukan dan dilaporkan terpisah.
- Partisi kualitas: seluruh sumber = di luar filter + tidak dapat ditentukan
  memenuhi filter + dalam cakupan. Dalam cakupan = eligible + tanggal dikecualikan.
  KPI/grafik/tabel menggunakan eligible yang sama. Alasan tanggal bisa tumpang
  tindih pada record yang sama, sehingga jumlah alasan bukan jumlah record unik.

Semua baris sumber dipertahankan, termasuk anomali. Raw tanggal/nominal dan tipe
cell, sumber/sheet/baris, hash file, serta warning tersimpan. Tidak menggunakan
no_rekening, menyambung historis ke aktif/transaksi, atau menghapus baris yang
identik tanpa kunci sah. Tidak melatih model, membuat prediksi, atau menampilkan
tren outstanding/NPF dari kontrak selesai.

## Pemrosesan dan akses

`src.etl.historical` mengekstrak/validasi; `src.database.historical` memuat kandidat
dan publikasi atomik memakai mekanisme penguncian ETL existing. Identitas sumber,
sheet dan versi aturan menentukan idempotensi. Load merekonsiliasi jumlah baris,
eligible, target terlambat, nominal dan nominal NULL sebelum commit; tidak
menimpa versi terpublikasi. Kandidat tanpa eligible berstatus invalid.

Preview/publish memeriksa kandidat historical, versi aturan, rekonsiliasi dan
admin aktif. Publikasi dan pointer historical diperbarui dalam satu transaksi,
menyimpan hubungan publikasi sebelumnya; pointer aktif tidak diganti. Pengulangan
publikasi lama tidak memundurkan pointer. Fakta yang dirujuk publikasi immutable.

Layanan `get_historical_summary` memakai READ ONLY / REPEATABLE READ dan menetapkan
pointer historical sekali. Hanya kolom analitik yang dibaca, bukan raw_values.
Agregasi/filter berada di layanan; UI tidak berisi query atau klasifikasi tanggal.
Tidak ada cache global identitas/hasil. Guard executive diperiksa pada halaman
dan sebelum/sesudah tindakan baca. Admin saja tidak memperoleh halaman pimpinan.

## Langkah operator (skema/load sudah selesai; publikasi belum diizinkan)

Status terbaru dan perintah aktual: [HISTORICAL_PRODUCTION_CANDIDATE.md](HISTORICAL_PRODUCTION_CANDIDATE.md).
Kandidat 53 ready telah di-preview dan direkonsiliasi. Jangan mengulang
`--apply-schema` pada tabel yang sudah ada. Blok di bawah merupakan catatan
prosedur awal, bukan instruksi menerapkan skema lagi. Untuk peninjauan saat ini:
`--status` dan `--preview 53 --admin-id 1`.

Periksa konfigurasi DB_NAME dan tinjau/backup database sebelum DDL. Perintah
berikut mendokumentasikan alur yang kini sudah dijalankan sampai preview di bi_bmt;
publish belum dijalankan. Jangan memakai konfigurasi DB pengujian
pada server aplikasi produksi.

```powershell
# Validasi tanpa koneksi/penulisan DB (default juga dry-run).
.venv/Scripts/python.exe -m src.etl.load_historical --dry-run

# Sekali, setelah review migrasi: tambah satu tabel dan trigger historis.
.venv/Scripts/python.exe -m src.etl.load_historical --status
$adminId = [long](Read-Host 'ID admin aktif dari --status')
.venv/Scripts/python.exe -m src.etl.load_historical --apply-schema --admin-id $adminId

# Kandidat baru saja; belum publikasi. Catat ID hasil perintah ini.
.venv/Scripts/python.exe -m src.etl.load_historical --load --admin-id $adminId

$candidateId = [long](Read-Host 'ID kandidat historis dari hasil load')
.venv/Scripts/python.exe -m src.etl.load_historical --preview $candidateId --published-by $adminId

# Hanya setelah preview can_publish=true dan izin publikasi produksi terpisah.
# Konfirmasi BMT sudah dicatat; belum ada publikasi produksi pada pekerjaan ini.
.venv/Scripts/python.exe -m src.etl.load_historical --publish $candidateId --published-by $adminId

.\dev
```

CLI juga mendukung --file dan --sheet yang eksplisit. Tidak membuat akun atau
password. Log hanya agregat/kode error aman, tanpa nilai mentah, rekening,
identitas pribadi atau kredensial. Migrasi menolak menimpa tabel yang sudah ada;
kegagalan DDL perlu ditinjau operator karena MySQL DDL bukan transaksi atomik.

## Verifikasi

Enam tes awal lulus: klasifikasi/batas hari, load/publikasi idempotent/immutable,
agregasi/penyebut/filter/pengecualian, rollback load, UI/reset/guard, dan regresi
sidebar (`tests/historical-tests.log`). Empat pemeriksaan berikutnya lulus untuk
admin ditolak, perubahan pointer, guard dan navigasi dua role eksplisit
(`tests/historical-extra-tests.log`). Dua pemeriksaan akhir transaksi READ ONLY
(INSERT ditolak MySQL 1792) dan guard lulus (`tests/historical-readonly-tests.log`).
Tes kegagalan publikasi sesudah INSERT juga memverifikasi rollback: publikasi
lama tetap aktif dan kandidat baru tetap ready. Beberapa tes diulang hanya saat
kasusnya diperkuat; angka putaran bukan jumlah tes unik. Seluruh penulisan hanya
pada database baru bi_bmt_test_* melalui helper yang menolak bi_bmt.

Browser Chrome headless: app.py asli, akun sintetis dengan login Argon2id, DB
pengujian terpisah. Sebelum fixture dipublikasikan, halaman belum tersedia
diverifikasi; publikasi fixture terjadi hanya pada DB pengujian. Kemudian KPI
dibandingkan layanan, filter/kombinasi/reset/kosong diuji, sidebar buka/tutup,
navigasi Beranda/Marketing/Konsentrasi serta logout diperiksa.
Viewport: 1366×768, 1440×900, 982×776 DPR 1,25; tidak ada pengujian ponsel.
Tidak ada overflow horizontal halaman; tabel boleh scroll di wadahnya. Font
aktual Inter lokal, judul 28 px, plot 280 px, padding panel 24 px, radius 12 px.
HTML/aplikasi dibandingkan pada 1440×1600 CSS px, DPR 1, scale 1. Referensi offline
memakai aset lokal, termasuk glyph Material Symbols Rounded bawaan Streamlit
untuk label ikon Outlined; perbedaan glyph kecil ini tidak mengubah ukuran HTML.

Inspeksi menemukan judul sumbu terlalu dekat tick atas. Jarak dirapikan secara
scoped; browser visual diulang pada tiga viewport dengan assertion jarak minimal
3 px. Tes data/filter tidak diulang karena hanya CSS yang berubah. Bukti:
`docs/screenshots/historical/measurements.json`, `visual-final.json`, target HTML,
screenshot seluruh halaman tiga ukuran, belum tersedia, kosong, dan regresi.
Screenshot memakai data sintetis dengan anomali, bukan 3.709 record sumber aktual.
Screenshot penuh mempertahankan lebar/DPR dan menambah tinggi viewport.

Pada verifikasi awal 25 Oktober 2026, kompilasi lulus dan produksi diperiksa baca-saja: no_publication,
tabel historis belum ada. Fingerprint seluruh 14 tabel tetap identik:
`17451e2368b46fc8379bb2882362369463d0a070e585107aa3bab4aca31324fb`.
Saat verifikasi awal itu belum ada migrasi/pemuatan/publikasi produksi maupun
training. Penerapan berizin 3 November 2026 dicatat terpisah pada
HISTORICAL_PRODUCTION_CANDIDATE.md; publikasi, UAT, tren waktu dan model baru
tidak termasuk tahap penerapan kandidat.
