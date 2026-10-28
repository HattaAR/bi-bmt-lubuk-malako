# Font lokal untuk login

Inter dan Plus Jakarta Sans, subset Latin variable WOFF2, diambil pada
23 Oktober 2026 melalui layanan resmi Google Fonts. Kedua file ditanam sebagai
data URI oleh `src/auth/login_presentation.py`; browser tidak menghubungi CDN.
Font hanya diterapkan pada lingkup login, dengan fallback Segoe UI/Arial.

- Inter: https://github.com/google/fonts/tree/main/ofl/inter
- Plus Jakarta Sans: https://github.com/google/fonts/tree/main/ofl/plusjakartasans
- Lisensi lengkap disertakan di `inter-OFL.txt` dan `plusjakartasans-OFL.txt`.

Logo tetap memakai `assets/logo.png` existing. Grafik mengikuti referensi desain
UI pengguna dan dibangun dengan HTML/CSS lokal tanpa mengambil data aktual.
