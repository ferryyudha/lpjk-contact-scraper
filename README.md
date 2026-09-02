# LPJK PUPR Contact Scraper (WhatsApp & Email Extractor)

Aplikasi desktop Python dengan antarmuka modern (CustomTkinter) dan engine otomasi (Selenium) untuk mengekstrak **Data Kontak Badan Usaha Jasa Konstruksi (Nomor WhatsApp / HP, Email, Telepon Kantor, Alamat Lengkap, dan Nama Pimpinan)** dari portal resmi LPJK Kementerian PUPR:
[https://lpjk.pu.go.id/laporan-lpjk/sebaran/cari](https://lpjk.pu.go.id/laporan-lpjk/sebaran/cari)

---

## 🌟 Fitur Utama

1. **Ekstraksi Khusus Kontak**:
   - **Nomor WhatsApp**: Otomatis mendeteksi nomor seluler/HP, mengonversi ke format internasional (`628...`), dan menyertakan link klik langsung `https://wa.me/...`.
   - **Alamat Email**: Otomatis memvalidasi dan mengekstrak email perusahaan.
   - **Telepon Kantor**: Mendeteksi nomor PSTN/kabel lokal.
   - **Data Lengkap**: Nama Badan Usaha, Alamat Lengkap, Provinsi, Kabupaten/Kota, NPWP, Nama Pimpinan (PJBU), dan Kualifikasi.

2. **Ekspor Siap Pakai**:
   - **Excel (.xlsx)**: Dilengkapi dengan formula link WhatsApp aktif. Anda bisa langsung klik tombol "Chat WA" di Excel untuk membuka chat WhatsApp tanpa perlu simpan nomor dulu!
   - **CSV (.csv)**: Format UTF-8 siap diimpor ke CRM, broadcast tools, atau database.

3. **Penanganan Otomasi Cerdas**:
   - Terintegrasi dengan Google Chrome & Microsoft Edge bawaan Windows.
   - Karena portal LPJK memproteksi form dengan Google reCAPTCHA, aplikasi membuka browser secara otomatis, mengisi filter, dan memberi kemudahan bagi pengguna untuk mencentang reCAPTCHA. Begitu hasil pencarian muncul, aplikasi secara otomatis mengekstrak seluruh data, berpindah halaman (auto-pagination), dan menarik detail kontak.

---

## 🚀 Cara Menjalankan Aplikasi

### Cara 1: Menggunakan Shortcut Batch (Paling Mudah)
Cukup **klik dua kali** file `run_app.bat` di folder ini. Aplikasi akan langsung memeriksa dependensi dan membuka jendela desktop.

### Cara 2: Lewat Command Prompt / Terminal
1. Buka terminal di folder ini (`c:\xampp\htdocs\scraping`).
2. Jalankan perintah:
   ```bash
   python main.py
   ```

---

## 📋 Struktur File

- [main.py](file:///c:/xampp/htdocs/scraping/main.py): Entry point aplikasi.
- [gui.py](file:///c:/xampp/htdocs/scraping/gui.py): Antarmuka desktop modern menggunakan CustomTkinter.
- [scraper.py](file:///c:/xampp/htdocs/scraping/scraper.py): Mesin otomasi Selenium & parser regex kontak WA/Email.
- [export.py](file:///c:/xampp/htdocs/scraping/export.py): Generator file Excel (.xlsx) dengan link WA interaktif dan CSV.
- [run_app.bat](file:///c:/xampp/htdocs/scraping/run_app.bat): File batch Windows untuk 1-klik eksekusi.
- [requirements.txt](file:///c:/xampp/htdocs/scraping/requirements.txt): Daftar dependensi Python.
- [test_app.py](file:///c:/xampp/htdocs/scraping/test_app.py): Script pengujian dan verifikasi.
