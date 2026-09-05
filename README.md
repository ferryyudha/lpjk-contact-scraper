# LPJK Contact Scraper

Aplikasi desktop untuk mengekstrak data kontak badan usaha (WhatsApp, Link WA langsung klik, email, provinsi, kabupaten/kota) dari portal LPJK PUPR:
https://lpjk.pu.go.id/laporan-lpjk/sebaran/cari

Data bersumber dari halaman detail tiap perusahaan yang diambil secara aman via AJAX setelah user menyelesaikan verifikasi reCAPTCHA.

---

## Fitur Utama

- **Pencarian Fleksibel**: Filter berdasarkan nama badan usaha, NPWP, provinsi, kabupaten/kota, dan kualifikasi usaha.
- **Ekstraksi Kontak Akurat**: Mendeteksi nomor WhatsApp valid (operator seluler Indonesia 08xx/628xx), generate link `https://wa.me/...`, dan alamat email resmi perusahaan.
- **Scraping Serentak Bertingkat (Staggered Concurrency)**: Memproses pengambilan detail dalam batch (3 perusahaan) dengan jeda bertingkat (0s, 1.5s, 3.0s) dan interval acak 4.0–5.5 detik untuk kecepatan 2x–3x lebih cepat tanpa memicu burst request.
- **Anti-Rate Limit (HTTP 429)**: Global Circuit Breaker yang otomatis menghentikan antrean selama 40 detik jika server LPJK memberi peringatan rate-limit, lalu melanjutkan scraping secara aman.
- **Anti-Crash di Ratusan Data**: Smart Page Waiter untuk mendeteksi render DataTables dan retry navigasi 3 kali agar tidak berhenti mendadak saat server lambat di halaman tinggi.
- **Micro-Break Antar Halaman**: Jeda istirahat 10–12 detik antar-halaman untuk me-reset token bucket rate limiter Nginx server LPJK.
- **Second Pass Recovery**: Memproses ulang baris yang ter-skip di akhir sesi secara otomatis dan langsung memperbarui tampilan tabel.
- **Kolom Ekspor Ringkas & Relevan**: Hasil ekspor Excel (.xlsx) dan CSV (.csv) dirancang fokus untuk telemarketing/kontak:
  1. `No`
  2. `Nama Badan Usaha`
  3. `WhatsApp (62...)`
  4. `Link WhatsApp` (hyperlink langsung chat)
  5. `Email Perusahaan` (hyperlink mailto)
  6. `Provinsi`
  7. `Kabupaten / Kota`
- **Auto-Save Berkala**: Otomatis menyimpan progres setiap 50 data ke folder `hasil_scraping`.
- **Standalone Executable (.exe)**: Dapat dijalankan langsung tanpa perlu install Python (v1.0.5).

---

## Cara Menjalankan Aplikasi

### 1. Menggunakan File Executable (.exe) — Rekomendasi
Cukup jalankan file:
```text
dist/LPJK_Contact_Scraper.exe
```
*(Tidak memerlukan instalasi Python, driver Selenium sudah dibundel di dalam)*

### 2. Menjalankan dari Source Code (Python)

1. Install dependensi:
   ```bash
   pip install -r requirements.txt
   ```
2. Jalankan aplikasi:
   ```bash
   python main.py
   ```
   Atau klik dua kali pada `run_app.bat`.

---

## Alur Kerja

1. Tentukan filter pencarian (Provinsi, Kabupaten, Kualifikasi, atau Kata Kunci) di sidebar.
2. Klik **Mulai Scraping** — jendela browser Chrome/Edge akan otomatis terbuka.
3. Centang kotak **reCAPTCHA** di browser, lalu klik tombol **Search**.
4. Aplikasi akan otomatis mendeteksi hasil dan memproses data per halaman.
5. Jika ada baris yang ter-skip akibat jaringan, sistem otomatis menjalankan **Second Pass** di akhir.
6. Klik tombol **Ekspor Excel (.xlsx)** atau **Ekspor CSV (.csv)** untuk menyimpan file.

---

## Struktur File

- `main.py` — Entry point aplikasi
- `gui.py` — Tampilan antarmuka desktop (CustomTkinter)
- `scraper.py` — Otomasi Selenium, anti-429, auto-retry, dan second pass recovery
- `export.py` — Format ekspor Excel (.xlsx dengan styling & link) dan CSV
- `LPJK_Contact_Scraper.spec` — Konfigurasi build PyInstaller standalone
- `CHANGELOG.md` — Catatan riwayat versi dan pembaruan
- `NOTES.md` — Dokumentasi teknis arsitektur dan troubleshooting
- `requirements.txt` — Daftar dependensi Python

