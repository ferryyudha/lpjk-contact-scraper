# Changelog

Semua perubahan penting pada proyek ini akan dicatat dalam file ini.

Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.0.0/).

## [Unreleased]

## [1.0.5] - 2026-09-05

### Added
- **Scraping Serentak Bertingkat (Staggered Batch Concurrency)**: Pengambilan detail kontak dilakukan secara paralel per batch (3 perusahaan) dengan jeda bertingkat (0s, 1.5s, 3.0s) dan interval acak 4.0–5.5 detik untuk kecepatan 2x–3x lebih cepat tanpa memicu burst request.
- **Tampilan Instan di GUI**: Seluruh baris di halaman aktif (25 data) langsung dimunculkan ke tabel antarmuka sebelum pengambilan detail dimulai, dan kontak di-update secara real-time.
- **Global Circuit Breaker (HTTP 429)**: Otomatis mendeteksi batas rate-limit server LPJK dan melakukan pause terpusat selama 40 detik dengan hitungan mundur sebelum melanjutkan antrean.
- **Micro-Break Antar Halaman**: Istirahat berkala 10–12 detik setiap pergantian halaman untuk me-reset token bucket rate limiter Nginx server LPJK.
- **Anti-Crash di Ratusan Data (Smart Page Waiter & Retry 3x)**: Menunggu aktif hingga DataTables selesai merender halaman baru dan mencoba ulang navigasi hingga 3 kali jika server melambat di halaman tinggi (`OFFSET 500+`).
- **Pencegahan Memory Leak**: Penambahan flag Chromium `--disable-dev-shm-usage` dan timeout eksplisit agar browser stabil berjalan berjam-jam tanpa crash renderer.

## [1.0.4] - 2026-09-03

### Added
- **Auto-retry 2x** per baris saat fetch detail gagal, dengan cooldown 5–10 detik sebelum mencoba ulang.
- **Second Pass otomatis**: setelah seluruh halaman selesai diproses, baris yang masih ter-skip otomatis diproses ulang via AJAX langsung, dan kolom kontak di tabel GUI langsung terupdate tanpa perlu scraping ulang dari awal.
- Kolom ekspor disederhanakan: hanya menyimpan **No, Nama Badan Usaha, WhatsApp, Link WhatsApp, Email, Provinsi, Kabupaten/Kota** — menghapus kolom Telepon Kantor, Pimpinan/PJBU, NPWP, Kualifikasi, Alamat Lengkap, dan Status/Subklasifikasi.

## [1.0.3] - 2026-09-03

### Added
- Transparansi status log detail pada GUI: membedakan secara tegas antara data kontak yang memang tidak dicantumkan oleh perusahaan di LPJK vs request detail yang mengalami timeout/kegagalan server.
- Indikator cuplikan alamat pada log saat kontak tidak tercantum untuk membuktikan bahwa halaman detail berhasil ditarik dari LPJK.

## [1.0.2] - 2026-09-03

### Fixed
- Perbaikan `ImportError: cannot import name 'export_to_json' from 'export'` pada `gui.py` yang menyebabkan file `.exe` gagal dibuka (*crash* saat *startup*).
- Perbaikan bundel PyInstaller pada file `.exe` agar menyertakan seluruh submodul driver Selenium (Chrome & Edge) dan binary pendukung `selenium-manager` sehingga browser dapat terbuka secara otomatis tanpa pesan "Chrome tidak tersedia / Gagal membuka browser".

### Added
- Pembaruan file executable standalone (`dist/LPJK_Contact_Scraper.exe`) v1.0.2 siap pakai tanpa instalasi Python.

## [1.0.1] - 2026-09-03

### Fixed
- Pencegahan error HTTP 429 (Too Many Requests) dari server LPJK dengan menambahkan delay cerdas (1.5 - 2.5 detik) antar baris data dan pembatasan pagination menjadi 25 baris per halaman.
- Penanganan auto-cooldown dan retry otomatis ketika server LPJK merespons status 429.
- Pembersihan buffer modal DOM (`#smallBody`) sebelum dan sesudah request detail untuk mencegah duplikasi data kontak perusahaan sebelumnya ke perusahaan baru.

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
