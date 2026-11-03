# KPI pembiayaan aktif

Analisis Historis memakai definisi terpisah dari SQLRESULT selesai, bukan data
aktif atau NPF. Aturan tanggal/penyebut dan pengecualian didokumentasikan di
[HISTORICAL_ANALYSIS.md](HISTORICAL_ANALYSIS.md).
Unit hitung historis SQLRESULT adalah **record sumber**, bukan kontrak unik
yang terverifikasi. Seluruh baris tetap dihitung; perbandingan baris identik
hanya analisis dampak dan tidak mengganti kandidat. Lihat
[HISTORICAL_READINESS.md](HISTORICAL_READINESS.md) untuk audit dan konfirmasi
BMT bahwa nilai identik mewakili pembiayaan berbeda. Satu record tenor 300
tetap masuk analisis tanggal yang valid; filter eksperimen model bukan aturan BI.

Portofolio Marketing memakai kembali agregasi Konsentrasi dan definisi rasio
yang sama; penyebut setiap marketing adalah outstanding marketing dalam filter.
NPF gabungan dihitung dari total nominal. Lihat [MARKETING_PORTFOLIO.md](MARKETING_PORTFOLIO.md).

Konsentrasi sektor/marketing memakai agregasi dan definisi KPI bersama pada
snapshot publikasi yang sama. Porsi mengikuti ukuran outstanding atau kontrak;
NPF total bukan rata-rata NPF kelompok. Lihat [CONCENTRATION.md](CONCENTRATION.md).

Layanan: `src.database.active_kpis.get_active_kpis(marketing_id=None, sector_id=None)`.
Layanan internal untuk dipakai bersama halaman dashboard; guard role halaman
tetap diperlukan saat integrasi UI. Beranda kini menggunakannya (lihat
`docs/EXECUTIVE_HOME.md`); tidak ada training atau perubahan skema.

## Versi, filter, dan presisi

Setiap permintaan membuka transaksi MySQL **READ ONLY / REPEATABLE READ**.
Pointer `current_publications` dibaca tepat sekali melalui pembaca publikasi
existing. ID dataset dan kamus hasil pembacaan itu digunakan sepanjang permintaan,
termasuk jika publikasi baru aktif saat permintaan masih berjalan. Tidak memakai
MAX(id), kandidat ready terbaru, atau gabungan versi.

Satu agregasi SQL per kategori membentuk seluruh numerator, denominator,
nominal, dan komposisi. Filter `marketing_id` dan `sector_id` bersifat opsional,
digabung dengan AND, serta memakai ID dimensi, bukan nama/kode. Nilai wajib
integer positif dalam rentang BIGINT UNSIGNED, bukan bool atau teks SQL.
Nilai query memakai parameter binding. ID yang tidak menemukan fakta dalam
publikasi saat ini menghasilkan `empty_selection`, termasuk ID dimensi versi lain.

Join hanya many-to-one ke dimensi berdasarkan primary key. Setiap fakta dalam
cakupan harus menunjuk kamus terkait publikasi; mismatch ditolak, bukan
dihilangkan diam-diam dari nominal. Tidak ada join ke transaksi atau model.
Kode kategori selain L/KL/D/M, termasuk lookup tidak ditemukan, masuk UNKNOWN.

Nominal dari MySQL tetap `Decimal`. Persentase memakai konteks Decimal dengan
presisi 50 digit dan tidak dibulatkan di layanan. CLI JSON menyimpan Decimal
sebagai teks agar tidak berubah menjadi float. Pembulatan dua desimal pada
contoh tabel hanya untuk tampilan; jumlah persentase yang dibulatkan dapat
berbeda sedikit dari 100%.

## Rumus dalam cakupan yang sama

| Keluaran kpis | Rumus |
|---|---|
| active_contracts | COUNT fakta pada satu versi/filter |
| original_principal | SUM original_principal |
| outstanding_principal | SUM outstanding_principal |
| overdue_principal | SUM overdue_principal |
| contracts_with_arrears | COUNT fakta dengan overdue_principal > 0 |
| npf_outstanding | SUM outstanding_principal untuk kode KL/D/M yang dikenali |
| npf_percent | npf_outstanding / outstanding_principal × 100 |

`npf_contracts` pada hasil layanan adalah jumlah kontrak berkode KL/D/M,
berbeda dari `contracts_with_arrears`. Opsi `include_context=True` menyertakan
pilihan marketing/sektor, sumber, dan agregat temuan validasi dalam snapshot
publikasi yang sama; tidak mengembalikan rekening atau nilai mentah temuan.

Komposisi berisi L, KL, D, M, dan UNKNOWN: jumlah kontrak, outstanding,
persentase jumlah terhadap jumlah seluruh kontrak cakupan, serta persentase
outstanding terhadap outstanding seluruh cakupan. Kategori tanpa record
memiliki jumlah/nominal nol; persentase memerlukan denominator yang valid.

Tunggakan tidak menjadi numerator NPF dan tidak ditambahkan ke outstanding.
NPF kelompok bukan rata-rata rasio kelompok lain. Tanggal anomali, tanggal
NULL, serta model input ineligible tidak mengeluarkan kontrak dari KPI nominal.
Skor model tidak mengubah kolektibilitas atau KPI. Acuan 5% tidak dipakai
sebagai label kesehatan/keamanan BMT.

## Status dan metadata

Output memuat metadata publikasi/dataset/kamus beserta position_date/status,
filter yang diterapkan, `unknown_collectibility_contracts`, `availability`,
`npf_reason`, dan batas kemampuan fitur.

| Kondisi | status | Nominal/jumlah | NPF |
|---|---|---|---|
| Belum ada pointer publikasi | no_publication | None, bukan nol | None; no_publication |
| Publikasi ada, tidak ada record dalam cakupan | empty_selection | 0 dengan status kosong | None; empty_selection |
| Record ada, total outstanding nol | available* | Nilai aktual termasuk nol | None; zero_outstanding |
| Kategori tidak dikenali ada | partial | Seluruh nominal tetap dihitung | None; unknown_collectibility* |
| Record ada, outstanding > 0, kategori lengkap | available | Nilai aktual | Rasio Decimal, termasuk 0% yang sah |

Jika unknown dan outstanding nol terjadi bersamaan, status tetap partial;
npf_reason zero_outstanding, jumlah unknown tetap dilaporkan. Numerator
`npf_outstanding` hanya menjumlah kategori KL/D/M yang dikenali; adanya unknown
berarti NPF lengkap belum tersedia, bukan kategori itu dianggap Lancar.

`availability.nominal_kpis`, `npf`, `composition`, `contract_shares`, dan
`outstanding_shares` menjelaskan bagian yang dapat digunakan. Saat outstanding
nol, persentase outstanding komposisi None, tetapi persentase jumlah kontrak
tetap tersedia. Saat belum ada publikasi, composition kosong. Saat filter
kosong, lima kategori tetap ada dengan jumlah/nominal nol dan persentase None.

KPI ini hanya BI statis. `position_based_features` dan `position_trends` tetap
false; tidak ada indikator jatuh tempo 7/14/30 hari, tren bulanan, atau perubahan
antarperiode. Tanggal posisi tidak diisi dari waktu komputer/publikasi.

## CLI baca-saja

Dari root proyek:

```powershell
.venv/Scripts/python.exe -m src.database.check_active_kpis

$marketingId = [int](Read-Host 'ID dimensi marketing publikasi aktif')
$sectorId = [int](Read-Host 'ID dimensi sektor publikasi aktif')
.venv/Scripts/python.exe -m src.database.check_active_kpis --marketing-id $marketingId --sector-id $sectorId
```

Kedua filter dapat digunakan sendiri-sendiri. CLI tidak menerima ID dataset
untuk melewati pointer. Output hanya agregat dan metadata, tanpa rekening atau
detail kontrak. Pesan driver MySQL disaring. Kondisi no_publication, kosong,
dan partial merupakan hasil baca yang sah (exit 0); periksa status/availability.
Konfigurasi/filter invalid atau relasi data tidak konsisten menghasilkan exit 1.

## Verifikasi 22 Oktober 2026

Pointer aktual menunjuk publikasi 1, dataset 34, kamus 33. ID tersebut hanya
hasil pemeriksaan, tidak ditanam dalam implementasi. Posisi tetap NULL/unknown.

| KPI aktual tanpa filter | Hasil |
|---|---:|
| Kontrak aktif | 427 |
| Pinjaman awal | 9654562435.00 |
| Outstanding pokok | 6497629974.00 |
| Tunggakan pokok | 213735116.00 |
| Kontrak menunggak pokok | 62 |
| Outstanding KL+D+M | 260089849.00 |
| NPF | 4.0028418060237174102890827374775342970307468604398% |
| Kategori tidak dikenali | 0 |

| Kolektibilitas | Kontrak | Outstanding | % kontrak | % outstanding |
|---|---:|---:|---:|---:|
| L | 400 | 6237540125.00 | 93.68 | 96.00 |
| KL | 6 | 73550318.00 | 1.41 | 1.13 |
| D | 9 | 110614551.00 | 2.11 | 1.70 |
| M | 12 | 75924980.00 | 2.81 | 1.17 |
| UNKNOWN | 0 | 0.00 | 0.00 | 0.00 |

69 tes lulus tanpa skip: 56 regresi existing dan 13 KPI/CLI baru. Pengujian
mencakup rumus, filter dan irisannya, kosong, penyebut nol, kategori tak dikenal,
kamus salah, larangan menulis di transaksi KPI, dan perubahan pointer saat satu
permintaan berjalan. Seluruh fixture ditulis hanya ke database bi_bmt_test_*;
suite memakai bi_bmt_test_kpi_suite_20261022_d1, tes KPI memakai database baru
tersendiri melalui helper yang menolak bi_bmt. Kompilasi Python lulus.
CLI aktual serta query SQL independen merekonsiliasi kontrol awal dan memastikan
kontrak baris 130 tetap termasuk dalam 427 fakta.
Fingerprint isi seluruh tabel bi_bmt sebelum/sesudah pengujian dan CLI identik;
publikasi, autentikasi, fakta, kamus, serta temuan tetap tidak berubah.

## Daftar tinjauan Beranda

Riwayat publikasi/unggah tidak menyediakan snapshot KPI per periode. Halaman
Riwayat & Tren membatasi perbandingan sampai tanggal posisi dan kesebandingan
terbukti; sumber, batasan, dan verifikasinya ada di `docs/HISTORY_TRENDS.md`.
Halaman Model & Metodologi mendokumentasikan definisi tersebut tanpa menjalankan
model; status bukti eksperimen dan verifikasinya ada di `docs/MODEL_METHODOLOGY.md`.

Halaman Kualitas Portofolio juga memakai snapshot layanan KPI yang sama.
Setiap elemen `composition` kini menyertakan `overdue_principal` (SUM tunggakan
pokok kategori), sehingga total kategori sama dengan total tunggakan cakupan.
Ini tidak mengubah rumus NPF. Lihat `docs/PORTFOLIO_QUALITY.md` untuk tampilan,
sorotan kategori, dan batas fungsi yang tersedia.

Dengan `include_context=True`, layanan juga mengembalikan `context.review`
(empat baris awal dan jumlah seluruh kontrak yang perlu ditinjau). Pembaca
`src.database.active_review.read_review` menggunakan cursor transaksi yang sama,
publikasi yang sudah ditetapkan, dan filter AND yang sama. Kriteria:
overdue_principal > 0 atau kode KL/D/M; satu fakta dihitung sekali. Urutan stabil:
tunggakan terbesar, outstanding terbesar, ID fakta. Tidak membaca rekening asli.
Kode anonim mengikat ID dataset dan fakta; tanggal jatuh tempo NULL tetap NULL.
