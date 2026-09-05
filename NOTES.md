# NOTES.md

Catatan keputusan aneh dan hal-hal yang perlu diingat kalau nanti balik ke project ini.

---

## Kenapa pakai Selenium, bukan requests biasa?

Form pencarian di lpjk.pu.go.id diproteksi Google reCAPTCHA v2.
POST langsung ke `/searching` tanpa token captcha valid → redirect balik ke halaman kosong.
Jadi mau tidak mau harus buka browser beneran, biarkan user centang captcha, baru ambil data dari halaman hasil.

Dua pendekatan yang sempat dicoba sebelum settle di ini:
- Requests + session cookie → tetap kena redirect, token captcha tidak bisa di-fake
- Selenium headless → captcha langsung gagal karena browser headless terdeteksi

Akhirnya: Selenium non-headless, user centang manual, app deteksi token terisi lalu auto-submit.

---

## Nomor telepon di halaman detail banyak yang bukan nomor HP

LPJK menyimpan nomor SBU, nomor registrasi, dan kode sertifikat di field yang sama dengan kontak.
Format angkanya mirip nomor HP (10-13 digit), jadi regex `\d{10,}` polos akan banyak false positive.

Solusinya: validasi prefix operator, bukan cuma panjang digit.
Prefix yang dipakai: `081x`, `082x`, `083x`, `085x`, `087x`, `088x`, `089x` sesuai alokasi Kominfo.
Nomor seperti `023040321094` tidak cocok dengan prefix manapun → dibuang.

Kelemahannya: nomor dari operator baru atau MVNO yang belum masuk daftar juga ikut terbuang.

---

## Kenapa detail kontak diambil lewat AJAX bukan klik tombol satu-satu?

Setiap baris tabel punya tombol "Detail" yang buka modal.
Kalau klik satu-satu: tunggu modal muncul, ambil HTML, tutup modal, lanjut ke baris berikutnya.
Terlalu lambat untuk ribuan data.

Alternatif: inject `$.ajax()` langsung dari Selenium lewat `execute_async_script`.
Ini jauh lebih cepat karena tidak perlu render modal, cukup ambil response HTML-nya.
jQuery sudah ada di halaman LPJK, jadi bisa langsung dipakai.

Fallback ke klik modal tetap ada kalau AJAX gagal (misalnya URL detail berubah format).

---

## Kenapa DataTables di-set ke 25 baris per halaman?

Awalnya dicoba 100 baris per halaman. Namun server LPJK sangat sensitif terhadap frekuensi request detail AJAX.
Dengan 100 baris, server sering merespons dengan status `HTTP 429 Too Many Requests`, menyebabkan data detail perusahaan menduplikasi data sebelumnya karena modal DOM `#smallBody` tidak sempat di-refresh.
Oleh karena itu, pagination diturunkan ke `25` baris per halaman dan diberi jitter delay 1.5 - 2.5 detik per baris untuk menjaga kestabilan koneksi.

---

## Mekanisme Anti-Rate Limiting (HTTP 429) & Duplikasi Data

1. **Pre-clear DOM Modal**: Setiap kali memanggil request detail, konten `#smallBody` dikosongkan terlebih dahulu via `$('#smallBody').empty()` agar data perusahaan sebelumnya tidak tertinggal.
2. **Auto-Cooldown Backoff**: Jika server LPJK mengembalikan status HTTP 429, scraper berhenti sejenak (cooldown 15-30 detik) lalu mencoba kembali.
3. **In-Place Auto-Retry (2x)**: Jika request detail timeout/gagal, otomatis dicoba ulang hingga 2 kali dengan jeda progresif (5s, 10s).
4. **Second Pass Recovery**: Baris yang tetap gagal/ter-skip akan dikumpulkan ke dalam list `skipped_items`. Setelah semua halaman selesai, dilakukan proses *second pass* secara otomatis dengan request langsung ke endpoint detail dan mengupdate baris yang ada di antarmuka GUI secara real-time.

---

## Penyederhanaan Kolom Ekspor (v1.0.4)

Kolom seperti `No Telepon Kantor`, `Pimpinan / PJBU`, `NPWP`, `Kualifikasi`, `Alamat Lengkap`, dan `Status / Subklasifikasi` dihapus dari berkas ekspor.
Fokus ekspor adalah data kontak cepat untuk outreach:
- `No`
- `Nama Badan Usaha`
- `WhatsApp (62...)`
- `Link WhatsApp`
- `Email Perusahaan`
- `Provinsi`
- `Kabupaten / Kota`

---

## Selector yang rapuh dan kemungkinan rusak

Semua ini bergantung pada struktur HTML portal LPJK per saat ini:

- `#TABLE_1` → ID tabel hasil pencarian
- `#TABLE_1_length` → dropdown jumlah baris per halaman
- `#TABLE_1_next` → tombol halaman berikutnya
- `#TABLE_1_info` → text "Showing X to Y of Z entries" untuk deteksi total data
- `a[data-attr]` atau `#smallButton` → tombol detail per baris
- `#smallBody` → konten modal detail
- `#smallModal .close` → tombol tutup modal
- `iframe[src*='recaptcha/api2/anchor']` → frame captcha untuk auto-klik
- `#g-recaptcha-response` → hidden input tempat token captcha disimpan

---

## Auto-save setiap 50 baris

Bukan 100 atau 10. Alasannya:
- Terlalu sering (tiap baris) → I/O jadi bottleneck, scraping melambat
- Terlalu jarang (tiap 500) → kalau browser crash atau internet putus, banyak data hilang

50 terasa cukup sebagai trade-off. Bisa diganti di konstanta `AUTOSAVE_INTERVAL` di `scraper.py`.

---

## Bundel Standalone Executable (PyInstaller)

Agar Selenium dan WebDriver dapat berjalan mulus di komputer user tanpa Python:
- `LPJK_Contact_Scraper.spec` menggunakan `collect_all('selenium')` dan `collect_all('webdriver_manager')`.
- Menjamin modul subpackage dynamic import dan binary `selenium-manager.exe` disertakan ke dalam bundel `.exe`.

---

## Arsitektur Scraping Serentak (Staggered Concurrency) & Pencegahan HTTP 429

Sebelumnya, pengambilan detail kontak dilakukan murni serial baris demi baris, yang memakan waktu lama dan rentan terkena blokir HTTP 429 saat frekuensi tidak terkendali.

Pada arsitektur baru:
1. **Pemisahan Tampilan & Pengambilan Detail**:
   - Seluruh baris di halaman aktif (25 baris) langsung diekstrak kolom dasarnya (Nama BU, NPWP, Provinsi, Kabupaten) dan dimasukkan ke tabel GUI seketika. Pengguna langsung melihat daftar perusahaan tanpa menunggu.
2. **Batch Asynchronous dengan Staggered Offset**:
   - Baris diproses dalam batch kecil (`BATCH_SIZE = 3`).
   - Request tidak dikirim serentak di milidetik yang sama (yang dapat memicu lonjakan/burst rate limiter Nginx).
   - Menggunakan `Promise.all` dan `setTimeout` di JavaScript browser:
     - Request 1: $t = 0.0$ detik
     - Request 2: $t = 1.5$ detik
     - Request 3: $t = 3.0$ detik
   - Memberikan jeda antar-batch sebesar `4.0 - 5.5` detik (`BATCH_INTERVAL_MIN` dan `BATCH_INTERVAL_MAX`).
3. **Pencegahan HTTP 429 Terpusat (Global Circuit Breaker)**:
   - Jika salah satu response dalam batch menghasilkan status HTTP 429, sistem langsung mengaktifkan jeda cooldown 40 detik (`HTTP_429_COOLDOWN`).
   - Batch yang gagal akan otomatis dicoba kembali setelah cooldown selesai.
4. **Micro-Break Antar Halaman (10–12 detik)**:
   - Sebelum berpindah ke halaman berikutnya (`TABLE_1_next`), diberikan jeda istirahat 10–12 detik (`PAGE_COOLDOWN_MIN` - `PAGE_COOLDOWN_MAX`).
   - Jeda ini mereset token bucket Nginx pada server LPJK sehingga kuota request per IP kembali segar.

---

## Mekanisme Anti-Crash di Ratusan Data (Robust Pagination & Memory Stability)

Saat scraping mencapai ratusan hingga ribuan baris, sering timbul masalah server LPJK melambat merespons pagination (`OFFSET` database backend besar) atau browser renderer kehabisan memori:

1. **Smart Page Transition Waiter (`_wait_for_new_page`)**:
   - Menghindari pembacaan tabel yang masih bertuliskan "Loading..." atau "Processing...".
   - Memastikan baris pertama halaman baru benar-benar berbeda dari baris pertama halaman sebelumnya sebelum mulai mengekstrak data.
2. **Retry Navigasi 3x (`_navigate_to_next_page`)**:
   - Jika tombol Next mengalami `StaleElementReferenceException` atau terhalang sementara, scraper tidak langsung berhenti (`break`), melainkan mencoba kembali hingga 3 kali dengan jeda pemulihan 3 detik.
   - Scraper hanya mengakhiri loop jika tombol Next terkonfirmasi memiliki atribut `disabled` (halaman terakhir).
3. **Penanganan Timeout Eksekusi Script**:
   - Jika server LPJK mengalami transient network hang saat eksekusi batch AJAX, sistem menangkap timeout secara elegan, memberi cooldown 10 detik, dan mencoba kembali batch tersebut tanpa membuat aplikasi crash.
4. **Argumen Stabilitas Memori Chromium**:
   - Menambahkan `--disable-dev-shm-usage`, `--disable-features=Translate,OptimizationHints`, serta timeout driver eksplisit (`set_script_timeout(35)` dan `set_page_load_timeout(60)`) agar browser stabil berjalan berjam-jam.

