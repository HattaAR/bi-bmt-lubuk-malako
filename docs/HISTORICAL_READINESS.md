# Kesiapan historis SQLRESULT — 3 November 2026

Status terbaru: **BMT mengonfirmasi baris identik adalah pembiayaan berbeda**;
penahanan karena ketidakjelasan tersebut sudah diselesaikan untuk hash/sheet
yang dikonfirmasi. Seluruh **3.709 record** tetap dipertahankan. Dengan izin
penulisan lanjutan 3 November 2026, skema sudah diterapkan dan kandidat produksi
**53 berstatus ready**; preview mengizinkan dan rekonsiliasi lulus.
**Belum ada publikasi historis.** Backup privat, hasil penerapan dan perintah
peninjauan aktual: [HISTORICAL_PRODUCTION_CANDIDATE.md](HISTORICAL_PRODUCTION_CANDIDATE.md).

## Keputusan bisnis BMT — 3 November 2026

Konfirmasi BMT disampaikan pengguna dalam percakapan tugas ini: 44 kelompok
bernilai identik merupakan pembiayaan berbeda yang kebetulan memiliki nilai sama,
bukan alasan membuang 45 record sebagai duplikasi ekspor. Keputusan
`BMT-HIST-2026-11-03-KEEP-ALL` dicatat di aturan `historical-v3-bmt-confirmed`,
terikat SHA-256 sumber di bawah dan sheet `SQLRESULT`. File atau sheet lain tidak
otomatis mewarisi konfirmasi ini. Perubahan kebijakan berikutnya memerlukan
versi aturan baru, bukan perubahan diam-diam pada kandidat terpublikasi.
ID tersebut adalah penanda internal aplikasi untuk keputusan yang disampaikan
pengguna, bukan nomor surat atau dokumen resmi BMT yang dibuat-buat.

Konfirmasi makna bisnis tidak menciptakan ID kontrak yang tidak ada dalam file.
Identitas teknis setiap record tetap `(versi, sumber, sheet, nomor baris Excel)`
dan `historical_fact_id` tersendiri. Penghitung UI tetap berbasis record.

## Sumber dan grain

`data/raw/historis/SQLRESULT.XLS`, sheet `SQLRESULT`, 1.073.664 byte, 24 kolom.
SHA-256: `ddcf0647dc2cead8a19c2878d2bcea9149ee2fc86d6cc3b288d16c364333df28`.
Seluruh baris tidak kosong dibaca. Grain penyimpanan adalah satu **record sumber
per versi**, beridentitas sumber/sheet/baris; SQLRESULT tidak memiliki ID kontrak
atau rekening. Keunikan kontrak tidak dapat dibuktikan dari kesamaan nominal,
tanggal, atau seluruh isi baris. Label penghitung Analisis Historis memakai
record; durasi kontrak tetap merupakan nama atribut tanggal, bukan klaim identitas.

Tanggal selesai adalah `tgl_akhir_trans`, dibandingkan dengan `tgl_jatuh_tempo`
awal. Selesai setelah jatuh tempo = terlambat, sebelum/tepat = tepat waktu.
Realisasi, jatuh tempo, dan selesai harus valid; jatuh tempo/selesai tidak boleh
mendahului realisasi. Penyebut persentase adalah record bertanggal layak dalam
filter yang sama. Tidak ada perubahan parser/pivot tanggal, kelompok durasi,
nominal, klasifikasi, atau hubungan ke data aktif/transaksi.

## Validasi aktual dan analisis dampak

| Ukuran | Semua record, dipertahankan | Satu record per kelompok identik, sensitivitas lama yang tidak digunakan |
|---|---:|---:|
| Record sumber | 3.709 | 3.664 |
| Tanggal layak dianalisis | 3.709 | 3.664 |
| Dikecualikan karena tanggal | 0 | 0 |
| Tepat waktu | 2.286 | 2.259 |
| Terlambat | 1.423 | 1.405 |
| Tepat waktu / record layak | 61,633864% | 61,653930% |
| Terlambat / record layak | 38,366136% | 38,346070% |
| Total `jml_pinjaman` | Rp27.154.601.218,00 | Rp26.740.601.218,00 |
| Nominal tidak valid | 0 | 0 |

Pemeriksaan mencakup **nilai dan tipe sel pada seluruh 24 kolom**, bukan hanya
empat kolom analitik. Ditemukan 44 kelompok baris identik, melibatkan 89 record
dan 45 baris tambahan. Contoh lineage anonim: baris Excel 3/9, 4/5, dan 15/18.
BMT sudah mengonfirmasi bahwa record tersebut mewakili pembiayaan berbeda.
Hasil pemeriksaan kesamaan tetap disimpan sebagai **audit nilai identik**;
tidak lagi dinyatakan sebagai dugaan duplikasi ekspor untuk sumber ini.

Pengambilan satu baris per kelompok akan mengurangi 27 record tepat waktu,
18 terlambat, dan Rp414.000.000,00 nominal awal. Proporsi terlambat turun sekitar
0,020067 poin persentase. Berdasarkan konfirmasi BMT, penghapusan itu justru
membuang pembiayaan berbeda yang sah. Kedua jumlah record tersebut
bukan jumlah kontrak unik. Nominal ini adalah nominal awal historis, bukan
outstanding portofolio aktif, penerimaan kas, ataupun NPF.

Perbandingan hanya berada dalam audit/dry-run dan metadata kandidat. Loader
selalu memuat semua record. Tidak ada keluaran deduplikasi untuk mengganti
Excel, kandidat, atau pembaca dashboard.

## Perubahan dan kesiapan teknis

- `src.etl.historical`: audit seluruh kolom, sensitivitas terpisah, raw nilai/tipe
  lengkap dan lineage baris; batas kapasitas DECIMAL(18,2). Aturan audit baru
  `historical-v3-bmt-confirmed` menjadi bagian identitas kandidat. Parsing tetap memakai
  reader yang sudah tersedia; XLS dan XLSX didukung.
- `src.database.historical`: admin aktif wajib saat load, preview dan publish;
  GET_LOCK/transaksi ETL existing; rekonsiliasi jumlah record, eligible, terlambat,
  nominal dan nominal NULL, plus hash fakta/raw lineage, sumber dan temuan wajib.
  Manifest disimpan di JSON `scope_description` existing, tanpa kolom baru.
- Catatan audit `historical_identical_values_distinct_records` disimpan untuk
  setiap baris terlibat, dengan nomor baris, sumber dan penjelasan konfirmasi BMT.
  Severity tetap warning sebagai jejak pemeriksaan, bukan blocking. Untuk file
  aktual terdapat 89 catatan baris identik, tanpa penghapusan 45 record.
  Nama field JSON `duplicate_groups`, `duplicate_group_count` dan
  `duplicate_extra_records` dipertahankan demi kompatibilitas audit; artinya
  kelompok nilai sama dan banyaknya anggota setelah anggota pertama, bukan
  keputusan duplikasi ekspor. `identical_records=89` dan
  `identical_rows_decision` menjelaskan maknanya secara eksplisit.
- Preview memperlihatkan audit, sumber, warning, rekonsiliasi, dan publikasi
  sebelumnya. Jika validasi, guard dan integritas lulus, sumber terkonfirmasi
  menghasilkan `can_publish=true`, `publication_blocker=null` dan keputusan
  `confirmed_distinct_records_keep_all`. Sumber lain yang belum dikonfirmasi
  dan memiliki baris identik tetap ditahan dengan `awaiting_bmt_identical_rows`.
  Tidak ada flag CLI untuk melewati pemeriksaan integritas/guard.
- Skema minimal yang sudah ada tetap satu tabel `fact_pembiayaan_historis`,
  FK/lineage/CHECK dan tiga trigger INSERT/UPDATE/DELETE. Loader/publisher
  menolak tabel non-InnoDB atau perlindungan yang belum lengkap. DDL MySQL
  auto-commit; migrasi menolak menimpa tabel existing. Kegagalan parsial perlu
  peninjauan operator, bukan penghapusan atau penerapan ulang otomatis.
- Pembaca menetapkan pointer `historical` sekali dalam transaksi READ ONLY /
  REPEATABLE READ; tidak membaca Excel. Publikasi aktif dan kamus tetap terpisah.
  Pembacaan publikasi v1/v2 tetap kompatibel; calon publikasi baru memerlukan
  audit v3 dan keputusan bisnis yang cocok. Kandidat v2 existing tidak ditimpa;
  versi aturan baru membentuk identitas kandidat baru. Produksi kini memiliki
  kandidat 53 ready, tetapi belum memiliki publikasi historis.

## Kondisi produksi yang diperiksa baca-saja

MySQL 8.4.3; setelah penerapan ada 15 tabel InnoDB dan kandidat historis 53 ready;
tidak ada pointer historis. Pointer aktif tetap publikasi 1, dataset 34, kamus 33. Angka ID ini
hanya hasil pemeriksaan, bukan nilai yang ditanam dalam implementasi.
Analisis Historis tetap menampilkan **belum tersedia**.

Pada tahap persiapan tanpa izin penulisan, fingerprint seluruh 14 tabel cocok.
Pada tahap penerapan terbaru, tambahan historis diverifikasi terpisah: semua
record existing, akun, fakta aktif dan pointer lama tetap sama; hanya satu tabel,
tiga trigger serta tambahan metadata/fakta kandidat 53 yang ditemukan. Excel raw
dan `dev.cmd` tetap cocok hash. Bukti persiapan: `docs/screenshots/historical-readiness/`:
`integrity-before.json`, `integrity-after.json`, `source-audit.json`,
`integration-final.log`, dan `tests.json`. Direktori bukti diabaikan Git;
skrip yang perlu dipelihara berada di `scripts/` dan tes di `tests/`.

## Pengujian sebelumnya yang masih berlaku

10 tes tanpa database lulus: audit dan sensitivitas tanpa kehilangan record,
perbedaan kolom nonanalitik, dry-run tanpa koneksi DB, istilah UI, klasifikasi
tanggal/batas hari, regresi batang/kelompok kosong/penyebut, serta pencarian dan
unduhan definisi Metodologi. Koreksi istilah record juga diterapkan pada definisi
indikator dan label sumber Metodologi; tata letak dan informasi model tidak berubah.

12 tes integrasi terarah lulus pada database baru `bi_bmt_test_*`, tanpa skip:
CLI migrasi dengan guard, status, load/preview/publish sintetis, load/publish
ulang, pembaca dashboard tanpa Excel, pemisahan pointer aktif/historis, publikasi
lama tidak memundurkan pointer, warning baris identik dan penahanan publikasi,
admin/role/nonaktif, manifest/temuan yang berubah, trigger hilang, tiga operasi
fakta terpublikasi ditolak, rollback load/publish, filter/pengecualian, snapshot
konsisten, READ ONLY dan AppTest aplikasi asli untuk filter/reset/guard.

Dua kegagalan awal fixture terjadi karena file sintetis berlainan nama ternyata
berisi byte identik; itu identitas sumber yang sama. Fixture independen diberi
penanda batch sintetis berbeda, pasangan baris identik dalam setiap file tetap
dipertahankan. Tes tidak dilonggarkan. Setelah penambahan pemeriksaan skema/audit,
12 tes integrasi terdampak dijalankan kembali dan lulus. Kompilasi modul terkait
dan pemeriksaan whitespace diff lulus. AppTest bukan inspeksi visual browser;
tidak dilakukan redesign atau pemeriksaan browser baru dalam tugas kesiapan ini.

Akun pada database pengujian dinonaktifkan setelah tes; riwayat tes dipertahankan.
Tidak dibuat file password/kredensial atau server aplikasi baru dalam tugas ini.

## Verifikasi keputusan BMT terbaru

Empat tes unit/audit terarah lulus: keputusan terikat hash/sheet yang benar,
tenor 300 tidak mengecualikan record bertanggal valid, seluruh record tetap ada
meskipun nilainya identik, dan dry-run tidak membuka database. Sembilan tes
integrasi terdampak lulus menggunakan database baru `bi_bmt_test_*`, mencakup:

- 3.709 record sintetis dengan 44 kelompok identik/45 baris tambahan tetap
  tersimpan sebagai 3.709 lineage baris berbeda; nominal Rp371.270,90 cocok,
  load ulang memakai ID versi yang sama, dan preview mengizinkan keputusan
  konfirmasi sintetis yang terikat hash sumber tersebut.
- Dua record bernilai identik memperoleh ID fakta tersendiri, catatan audit,
  dan tetap utuh sesudah publikasi sintetis/idempotensi. Preview tidak
  memublikasikan otomatis.
- Sumber tanpa konfirmasi tetap ditahan. Audit/keputusan yang dimodifikasi,
  warning hilang dan blocking tetap ditolak. Guard admin/nonaktif, perlindungan
  fakta terpublikasi, pemisahan pointer, serta rollback load/publish tetap lulus.

Tes berukuran 3.709 record sempat gagal pada query pemeriksa tes karena alias
SQL `lines` adalah kata khusus MySQL. Alias diperbaiki menjadi `source_lines`,
kemudian hanya tes tersebut diulang dan lulus; implementasi loader tidak
dilonggarkan. Tes itu diulang sekali lagi untuk menyimpan keluaran preview
database yang benar-benar dihasilkan pada `preview-confirmed-synthetic.json`.
Nilai sintetis tidak boleh dibaca sebagai nominal sumber nyata.

`source-audit-bmt-confirmed.json` tetap merupakan dry-run file aktual, sedangkan
`preview-confirmed-synthetic.json` tetap merupakan bukti sintetis. Setelah izin
lanjutan, **preview produksi nyata ID 53** tersedia di
`docs/screenshots/historical-production-load/preview.json`: ready,
can_publish=true, 3.709 record, rekonsiliasi lulus dan 89 catatan audit.
Audit versi sebelumnya tetap disimpan sebagai jejak keputusan awal, yang telah
digantikan konfirmasi BMT. Jangan mencampur nominal/ID fixture dan produksi.

## Record tenor 300 dan notebook lama

Pemeriksaan sumber aktual menemukan tepat satu record:

| Atribut | Nilai |
|---|---|
| Sheet / baris Excel asli | SQLRESULT / 2880 |
| `bi_jangka_waktu` mentah | 300; satuannya belum dikonfirmasi |
| `jml_pinjaman` | Rp250.000.000,00 |
| Realisasi | 17 Oktober 2024 |
| Jatuh tempo awal | 17 Oktober 2029 |
| Selesai (`tgl_akhir_trans`) | 25 Juni 2025 |
| Durasi dari tanggal | 1.826 hari |
| Status analisis dashboard | Layak; tepat waktu; 0 hari keterlambatan |
| Temuan tanggal | Tidak ada |

Kedua lampiran notebook dibaca sebagai JSON, tidak dijalankan, tidak dilatih,
dan tidak dimodifikasi. Penomoran sel berikut adalah urutan sel notebook mulai
dari 1, bukan nomor eksekusi:

- **LightGBM_6_fitur.ipynb**, sel 4: filter eksplisit
  `df = df.loc[df["bi_jangka_waktu"] != 300].copy()`, lalu reset indeks.
  Output tersimpan: satu baris dikeluarkan, tersisa 3.708; target 0 = 2.285 dan
  target 1 = 1.423. Tidak ada justifikasi bisnis pada filter tersebut.
  SHA-256 notebook:
  `add390b32a08763a441af0a1b1d827daf594b6f415f38bdf4db961781e9fb129`.
- **lightgbm_8_fitur.ipynb**, sel 4: kondisi historis
  `d["bi_jangka_waktu"].eq(300)` diberi alasan
  **“Eksklusi tenor 300 sesuai eksperimen sebelumnya”**. Komentar menyebut
  mempertahankan filter eksperimen sebelumnya. Sel 5 memisahkan record itu;
  keluaran tersimpan menunjuk baris Excel 2880 dengan alasan tersebut, historis
  untuk eksperimen 3.708 dan dipisahkan 1. Tidak ada alasan bisnis tambahan yang
  membuktikan nilai 300 salah. SHA-256 notebook:
  `c6c561afaf3b83d45609ddcc902fd07c0650d047016f24d94e028f68cac19084`.

Keduanya merujuk nama sumber SQLRESULT.XLS; hash file input eksperimen tidak
tercatat sehingga kesamaan byte input notebook dengan file lokal tidak diklaim.
Jumlah dan record yang ditampilkan pada output tersimpan cocok dengan
pemeriksaan lokal di atas. Output tersebut adalah bukti tersimpan, bukan hasil
menjalankan ulang eksperimen. Metadata notebook ini tidak mengaktifkan model
atau skor pada aplikasi.

**Keputusan dashboard:** tidak menerapkan filter eksperimen `tenor != 300`.
Tanggal record ini lolos validasi; raw tenor tetap disimpan. Satuan tenor atau
kelayakan fitur model masih perlu dikonfirmasi untuk penggunaan model, tetapi
tidak membatalkan analisis penyelesaian berdasarkan tanggal yang valid.
Selisih dashboard (3.709 / 2.286 / 1.423) dengan notebook
(3.708 / 2.285 / 1.423) dijelaskan oleh satu record tepat waktu tersebut.

## Langkah operator — skema/load selesai, berhenti sebelum publish

**Status terbaru:** bagian di bawah menjelaskan prosedur penerapan; skema dan
load sudah dijalankan dengan izin lanjutan dan backup terverifikasi. Jangan
mengulang `--apply-schema`; tabel sudah ada. Untuk pekerjaan saat ini cukup
`--status` dan `--preview 53 --admin-id 1`. Riwayat perintah aktual dan backup:
[HISTORICAL_PRODUCTION_CANDIDATE.md](HISTORICAL_PRODUCTION_CANDIDATE.md).

Dari root proyek, dua perintah pertama aman baca-saja/dry-run:

```powershell
.\.venv\Scripts\python.exe -m src.etl.load_historical --status
.\.venv\Scripts\python.exe -m src.etl.load_historical --file '.\data\raw\historis\SQLRESULT.XLS' --sheet SQLRESULT --dry-run
```

`--status` menampilkan database tujuan, keberadaan tabel/trigger, pointer, dan
ID admin aktif yang benar-benar tercatat, tanpa username/password. Tidak membuat
akun. Pastikan DB_NAME mengarah ke tujuan yang memang diotorisasi. Jika tidak ada
admin aktif, siapkan akun melalui mekanisme admin proyek, bukan ID rekaan.

Prosedur skema/load berikut sudah dilaksanakan pada 3 November 2026 setelah izin
pengguna dan verifikasi backup. Variabel ID di bawah adalah pola dokumentasi;
hasil aktual adalah admin 1 dan kandidat 53. Jangan mengulang penerapan skema:

```powershell
$adminId = [long](Read-Host 'ID admin aktif dari --status')
.\.venv\Scripts\python.exe -m src.etl.load_historical --apply-schema --admin-id $adminId
.\.venv\Scripts\python.exe -m src.etl.load_historical --status
.\.venv\Scripts\python.exe -m src.etl.load_historical --file '.\data\raw\historis\SQLRESULT.XLS' --sheet SQLRESULT --load --admin-id $adminId

$candidateId = [long](Read-Host 'dataset_version_id dari hasil --load')
.\.venv\Scripts\python.exe -m src.etl.load_historical --preview $candidateId --admin-id $adminId
```

`--load` tidak memublikasikan. `ready` bukan izin publikasi. Tinjau hasil preview:
3.709 record/eligible, 1.423 terlambat, nominal awal Rp27.154.601.218,00,
rekonsiliasi lulus, keputusan BMT KEEP-ALL cocok, dan 89 catatan audit nilai
identik. `can_publish=true` hanya jika pemeriksaan wajib, guard dan integritas
lainnya juga lulus. Jangan mengubah JSON database atau warning untuk melewati
pemeriksaan. Berhenti setelah preview untuk tinjauan operator sebelum publish.

Sintaks publikasi eksplisit yang tersedia, hanya setelah keputusan tersebut
dicatat, preview mengizinkan dan tindakan publikasi produksi telah diotorisasi:

```powershell
.\.venv\Scripts\python.exe -m src.etl.load_historical --publish $candidateId --admin-id $adminId
.\dev
```

`--published-by` tetap alias `--admin-id` untuk CLI lama. Login sebagai executive,
buka Analisis Historis (`/analisis-historis`). Cocokkan record eligible,
tepat waktu/terlambat, serta rincian durasi dengan versi yang dipublikasikan.
Pembaca tidak memilih kandidat ready atau membaca file Excel saat filter berubah.

## Batas kesiapan

Makna 44 kelompok identik telah dikonfirmasi dan penahanan terkait sudah
diselesaikan. Sumber tetap tidak memiliki ID kontrak. Kesiapan data/aturan tidak
berarti publikasi otomatis. Produksi sudah dimigrasi, dimuat dan di-preview
secara eksplisit; kandidat 53 tetap ready dan belum dipublikasikan. Tahap berikut
hanya publikasi setelah diotorisasi terpisah.
Alasan bisnis eksklusi tenor 300 pada eksperimen belum diketahui dan tidak
diterapkan ke dashboard. Tidak ada tren posisi, scoring, training, atau
penyambungan historis/aktif baru yang diklaim.
