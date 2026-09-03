# Changelog

Semua perubahan penting pada proyek ini akan dicatat dalam file ini.

Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.0.0/).

## [Unreleased]

## [1.0.1] - 2026-09-03

### Fixed
- Pencegahan error HTTP 429 (Too Many Requests) dari server LPJK dengan menambahkan delay cerdas (1.5 - 2.5 detik) antar baris data dan pembatasan pagination menjadi 25 baris per halaman.
- Penanganan auto-cooldown dan retry otomatis ketika server LPJK merespons status 429.
- Pembersihan buffer modal DOM (`#smallBody`) sebelum dan sesudah request detail untuk mencegah duplikasi data kontak perusahaan sebelumnya ke perusahaan baru.
- Perbaikan `ImportError: cannot import name 'export_to_json' from 'export'` pada `gui.py` yang menyebabkan file `.exe` gagal dibuka (*crash* saat *startup*).

### Added
- Penyediaan file executable standalone (`dist/LPJK_Contact_Scraper.exe`) yang siap dijalankan langsung di Windows tanpa memerlukan instalasi Python.

## [1.0.0] - 2026-09-03

### Added
- Aplikasi desktop untuk scraping data kontak kontraktor LPJK (WhatsApp, email, telepon kantor, nama pimpinan, alamat lengkap).
- Filter pencarian berdasarkan kata kunci perusahaan/NPWP, provinsi, kabupaten/kota, dan kualifikasi usaha.
- Ekspor data ke Excel (.xlsx) dengan link chat WhatsApp aktif dan ke format CSV (.csv).
- Tombol ekspor cepat dan pembuka folder hasil tepat di atas tabel data.
- Mode pengambilan semua data secara otomatis tanpa batasan halaman.
- Fitur auto-save otomatis setiap 50 data ke folder hasil scraping.

### Fixed
- Tombol aksi di bagian bawah sidebar yang terpotong pada layar laptop atau display scaling besar.
- Tampilan teks dan kotak isian sidebar yang terpotong oleh batang scrollbar samping.
- Nomor resi atau kode perizinan yang keliru terbaca sebagai nomor kontak WhatsApp/telepon.
