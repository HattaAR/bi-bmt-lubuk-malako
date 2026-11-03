# Pemeriksaan kesiapan historis — kelanjutan

Tidak mengulang implementasi Analisis Historis. Instruksi terbaru pengguna:
pertahankan semua record, dugaan identik sebagai warning, sensitivitas terpisah,
tanpa penulisan pada bi_bmt dan tanpa klaim kontrak unik.

- [x] Baca diff, implementasi, baseline, dokumentasi dan dua tes awal yang belum selesai.
- [x] Buktikan kegagalan awal audit/CLI, lalu lengkapi raw seluruh kolom dan audit.
- [x] Validasi file aktual; bandingkan semua record versus satu baris per kelompok identik.
- [x] Simpan lineage, warning dan manifest menggunakan skema JSON existing.
- [x] Perkuat guard admin, kelengkapan skema, rekonsiliasi dan audit sebelum commit/publish.
- [x] Tahap awal memisahkan technical_ready dari can_publish; penahanan saat konfirmasi belum tersedia sudah digantikan keputusan KEEP-ALL di bawah.
- [x] Koreksi istilah penghitung UI menjadi record; pertahankan layout/rumus/key/URL.
- [x] Uji 10 unit/presentasi (termasuk dua regresi definisi) dan 12 integrasi sintetis terdampak; AppTest asli, bukan klaim browser.
- [x] Verifikasi CLI status/dry-run/migrasi/load/preview/publish pada tujuan yang diizinkan.
- [x] Kompilasi dan diff whitespace; dokumentasi dan langkah operator.
- [x] Fingerprint produksi/skema/raw/dev cocok terhadap baseline; akun fixture dinonaktifkan.
- [x] Konfirmasi lanjutan BMT: pembiayaan berbeda bernilai sama, pertahankan semua record; aturan v3 terikat hash/sheet.
- [x] Penerapan skema/load historis di produksi — diotorisasi pada tahap lanjutan dan selesai sesudah backup terverifikasi.
- [ ] Publikasi historis produksi — tahap terpisah, belum diizinkan dan tidak dijalankan.

Hasil dan batas bukti: [HISTORICAL_READINESS.md](../../HISTORICAL_READINESS.md).

Kelanjutan setelah konfirmasi BMT:

- [x] Catat keputusan, pertahankan audit 44 kelompok/45 baris tambahan dan lineage seluruh record.
- [x] Hapus penahanan hanya untuk sumber terkonfirmasi; sumber lain, guard, integritas dan rekonsiliasi tetap diperiksa.
- [x] Baca kedua notebook lampiran sebagai JSON, tanpa eksekusi/training; telusuri tenor 300 pada baris Excel 2880.
- [x] Pertahankan tenor 300 pada dashboard: tanggal layak dan tepat waktu; alasan bisnis eksklusi eksperimen tidak diasumsikan.
- [x] Empat tes unit/audit dan sembilan integrasi terarah lulus; bukti sebelumnya yang masih relevan dipertahankan.
- [x] Siapkan dry-run aktual dan preview database sintetis yang dibedakan secara jelas; langkah operator diperbarui.
- [x] Penerapan skema, kandidat dan preview historis produksi — kandidat aktual 53 ready, rekonsiliasi dan preview lulus.
- [x] Backup privat diuji restore pada DB sementara dan cocok; database verifikasi/kredensial sementara dibersihkan.
- [x] Semua record existing, akun, fakta aktif, pointer, raw dan dev.cmd diverifikasi; hanya tambahan historis yang diizinkan ditemukan.

Hasil penerapan: [HISTORICAL_PRODUCTION_CANDIDATE.md](../../HISTORICAL_PRODUCTION_CANDIDATE.md).
