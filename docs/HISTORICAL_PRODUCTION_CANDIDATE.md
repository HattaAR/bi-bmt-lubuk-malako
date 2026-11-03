# Kandidat historis produksi — 3 November 2026

Otorisasi pengguna pada tahap ini: backup, penerapan skema historis yang diperlukan,
pemuatan seluruh SQLRESULT.XLS ke `bi_bmt`, rekonsiliasi dan preview kandidat.
**Publikasi belum diizinkan dan tidak dijalankan.**

## Backup sebelum perubahan

Backup privat yang dipertahankan:

`backups/historical-20261103T083058Z-29b8c57c/bi_bmt.sql.gz`

- mysqldump 8.4.3, sesuai MySQL server 8.4.3; single-transaction, seluruh 14 tabel
  beserta data, opsi trigger/routine/event disertakan (ketiganya kosong saat itu).
- Folder dibatasi ACL Windows untuk pengguna pemilik dan SYSTEM, tidak diwariskan
  ke pengguna lain. Direktori `backups/` diabaikan Git.
- Backup benar-benar dipulihkan memakai mysql client ke database sementara baru
  `bi_bmt_test_backup_*`. Seluruh isi tabel cocok, termasuk metadata akun tanpa
  menjalankan login atau mengubah akun produksi. Database sementara dihapus.
- Pemulihan menambahkan penulisan `CHARACTER SET utf8mb4` yang sebelumnya implisit
  pada beberapa kolom. Penyebab selisih hash DDL ditelusuri sebelum perubahan
  produksi. Verifikasi memakai DDL kanonik dan metadata kolom/foreign key aktual;
  tidak mengabaikan perbedaan tipe, default, collation, constraint atau data.
- Integritas gzip dan SHA-256 isi SQL diperiksa; isi/skema produksi tetap sama
  selama backup. Ukuran arsip **33.374 byte**. SHA-256 arsip:
  `a424212682ed1dd90f5e783f5866aed734da769eeb3181730956644dd53dfa1f`.
- Bukti privat: `verification.json` dan `production-before.json` dalam folder
  backup tersebut. File kredensial sementara dihapus. Empat salinan SQL percobaan
  verifikasi yang gagal telah dibersihkan; backup gzip terverifikasi dipertahankan.

Tidak ada migrasi atau load produksi sebelum verifikasi backup berhasil.

## Perubahan skema dan kandidat

Ditambahkan **satu tabel** `fact_pembiayaan_historis` (InnoDB), menggunakan
`src.database.historical_schema.apply_historical_schema` melalui CLI yang sudah
diuji. Tabel memuat FK versi/sumber, unique lineage versi-sumber-sheet-baris,
indeks versi/tahun, CHECK konsistensi tanggal/target, serta tiga trigger:

- `protect_historical_insert`
- `protect_historical_update`
- `protect_historical_delete`

Sekarang ada 15 tabel. Struktur 14 tabel existing tidak diubah. Pemuatan menambah
1 versi, 1 sumber, 1 hubungan sumber, 3.709 fakta dan 89 catatan validasi; isi
record existing pada tabel metadata tetap sama.

Kandidat aktual: **dataset_version_id 53**, **status ready**,
aturan `historical-v3-bmt-confirmed`. Admin ID **1** diperoleh dari pemeriksaan
akun aktif ber-role admin yang sudah ada; tidak dibuat atau diubah akun baru.

Sumber: `data/raw/historis/SQLRESULT.XLS`, sheet `SQLRESULT`, SHA-256
`ddcf0647dc2cead8a19c2878d2bcea9149ee2fc86d6cc3b288d16c364333df28`.
Seluruh 24 kolom mentah dan lineage disimpan. Seluruh record identik tetap
terpisah menurut baris sumber, sesuai keputusan BMT KEEP-ALL. ID kontrak tidak
diciptakan. Penjelasan keputusan/notebook: [HISTORICAL_READINESS.md](HISTORICAL_READINESS.md).

## Rekonsiliasi dan preview aktual

| Ukuran | Hasil database |
|---|---:|
| Record / lineage baris berbeda | 3.709 / 3.709 |
| Record bertanggal layak | 3.709 |
| Tepat waktu | 2.286 |
| Terlambat | 1.423 |
| Total nominal awal | Rp27.154.601.218,00 |
| Nominal tidak valid | 0 |
| Blocking | 0 |
| Catatan audit nilai identik | 89 record, 44 kelompok, 45 baris setelah anggota pertama |

Catatan menggunakan rule `historical_identical_values_distinct_records`, severity
warning: BMT mengonfirmasi pembiayaan berbeda bernilai sama. Catatan ini tidak
menahan publikasi. Tidak ada warning tanggal atau nominal lain pada kandidat ini.
Tenor 300 pada baris Excel **2880** tetap tersimpan: Rp250 juta, tanggal valid,
durasi 1.826 hari, target tepat waktu. Filter eksperimen notebook tidak diterapkan.

Preview produksi: `mode=preview`, `technical_ready=true`, `can_publish=true`,
`reconciliation=passed`, `publication_blocker=null`,
`previous_publication_id=null` (belum pernah ada publikasi historis).
Loader/publisher memverifikasi manifest fakta, raw lineage, audit, sumber dan
temuan wajib. Rekonsiliasi SQL independen cocok. Nilai SUM MySQL berupa Decimal
diserialisasikan CLI sebagai string JSON; perbandingan dilakukan numerik.

Pemuatan ulang mengembalikan **ID 53 yang sama dengan reused=true**, tanpa
tambahan fakta atau metadata. Tidak ada ETL otomatis dari halaman dashboard.

## Batas perubahan yang diverifikasi

- Pointer tetap hanya **active → publikasi 1 / dataset 34 / kamus 33**.
- `dataset_publications` tetap 1 record; **tidak ada publikasi/pointer historis**.
- Isi akun/role, fakta aktif, seluruh dimensi, record publikasi dan record metadata
  existing cocok dengan baseline per tabel. Hanya tambahan historis yang diizinkan
  ditemukan; 89 temuan semuanya terkait kandidat 53.
- Excel raw dan `dev.cmd` tetap cocok hash sebelum/sesudah. Tidak ada training,
  perubahan UI/login, commit/push atau penghentian server pengguna.
- Pembaca historis mengembalikan `no_publication`; dashboard tetap menampilkan
  belum tersedia sampai tindakan publikasi terpisah dilakukan.

Backup/restore, migrasi, load, SQL rekonsiliasi, preview, idempotensi dan pemeriksaan
integritas di atas dijalankan pada tahap ini. Suite pengujian aplikasi yang tidak
berubah tidak diulang; bukti unit/integrasi sebelumnya tetap berlaku. Dua skrip
operasional tambahan berada di `scripts/backup_before_historical.py` dan
`scripts/verify_historical_candidate_load.py`, bukan di folder bukti yang diabaikan Git.

Bukti agregat lokal di `docs/screenshots/historical-production-load/`:
`preflight.json`, `load.json`, `reconciliation.json`, `preview.json`,
`idempotent-reload.json`, `protected-before.json`, `protected-after.json`,
`backup-verification-summary.json`, dan `final-state.json`.

## Perintah peninjauan dan publikasi terpisah

Dari root proyek, aman untuk pemeriksaan ulang:

```powershell
.\.venv\Scripts\python.exe -m src.etl.load_historical --status
.\.venv\Scripts\python.exe -m src.etl.load_historical --preview 53 --admin-id 1
```

Skema sudah diterapkan; jangan mengulang `--apply-schema`. Perintah tersebut
memang menolak menimpa tabel existing.

**Perintah berikut belum dijalankan dan hanya untuk ditinjau, bukan izin publikasi:**

```powershell
.\.venv\Scripts\python.exe -m src.etl.load_historical --publish 53 --admin-id 1
```

Saat kelak diotorisasi, jalankan preview terlebih dahulu dan pastikan kandidat,
admin, source hash, warning dan rekonsiliasi masih sesuai. Tidak perlu memuat
ulang atau mengganti sumber/pointer aktif. Setelah publikasi terpisah berhasil,
halaman Analisis Historis akan mengambil pointer historis dari database.
