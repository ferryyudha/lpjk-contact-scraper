# LPJK Contact Scraper

Aplikasi desktop untuk mengekstrak data kontak badan usaha (WhatsApp, email, telepon, alamat, pimpinan) dari portal LPJK PUPR:
https://lpjk.pu.go.id/laporan-lpjk/sebaran/cari

Data bersumber dari halaman detail tiap perusahaan yang diambil via AJAX setelah user menyelesaikan reCAPTCHA.

## Cara install

```
pip install -r requirements.txt
```

Browser Chrome atau Edge harus sudah terinstall — ChromeDriver/EdgeDriver dikelola otomatis oleh Selenium Manager.

## Cara jalankan

```
python main.py
```

Atau klik dua kali `run_app.bat`.

## Alur kerja

1. Pilih filter (provinsi, kabupaten, kualifikasi, kata kunci) di sidebar kiri.
2. Klik "Mulai Scraping" — browser akan terbuka otomatis.
3. Centang reCAPTCHA di browser, klik Search.
4. Aplikasi akan mengambil data halaman per halaman secara otomatis.
5. Data di-auto-save setiap 50 baris ke `hasil_scraping/LPJK_AutoSave_Terbaru.xlsx`.
6. Ekspor manual via tombol di toolbar atas tabel.

## Dependency yang rawan error

- `selenium` — versi Chrome/Edge di sistem harus cocok. Jika browser diupdate tapi driver belum, bisa gagal connect.
- `customtkinter` — butuh Python >= 3.8. Tampilan bisa aneh di scaling Windows 150%+ jika versi lama.
- `openpyxl` — dipakai untuk generate `.xlsx` dengan hyperlink WA. Jangan pakai `xlwt` sebagai pengganti.

## Known issues

- Selector `#TABLE_1`, `#smallButton`, dan `a[data-attr]` bergantung pada struktur HTML portal LPJK.
  Kalau PUPR update tampilan situsnya, selector ini bisa berhenti berfungsi dan perlu diinspeksi ulang.
- reCAPTCHA otomatis hanya berhasil kalau token sudah di-solve sebelum form disubmit.
  Kadang browser perlu klik manual oleh user sebelum tombol Search aktif.
- Nomor telepon dengan format tidak standar (misal dipisah titik atau tanpa kode area) tidak akan terdeteksi.

## Struktur file

- `main.py` — entry point
- `gui.py` — antarmuka CustomTkinter
- `scraper.py` — Selenium automation + regex ekstraksi kontak
- `export.py` — ekspor ke Excel dan CSV
- `run_app.bat` — shortcut Windows
- `requirements.txt` — daftar dependency
