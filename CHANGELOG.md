# Changelog

Semua perubahan penting pada proyek ini akan dicatat dalam file ini.

Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.0.0/).

## [Unreleased]

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
