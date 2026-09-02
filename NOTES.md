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

## Kenapa DataTables di-set ke 100 baris per halaman?

Default-nya 10 baris. Berarti untuk 17.900 data butuh 1.790 kali pindah halaman.
Dengan 100 baris: cukup 179 halaman. 10x lebih cepat.

LPJK pakai DataTables standar, jadi tinggal set `select[name="TABLE_1_length"]` ke nilai `100`.
Kalau nilai `100` tidak ada di opsi dropdown DataTables-nya, fallback ke `50` lalu `25`.

---

## Selector yang rapuh dan kemungkinan rusak

Semua ini bergantung pada struktur HTML portal LPJK per saat ini (September 2025).
Kalau PUPR update tampilan, perlu dicek ulang:

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

## Export JSON tidak diekspos ke UI

Ada fungsi `export_to_json` di `export.py` tapi tidak ada tombolnya di GUI.
Belum diminta, jadi tidak dibuatkan. Kalau nanti perlu tinggal tambah tombol dan hubungkan.
Fungsinya sudah jalan, tidak perlu ubah apapun di `export.py`.

---

## Sidebar pakai CTkScrollableFrame

Awalnya pakai `CTkFrame` biasa.
Di monitor dengan scaling Windows 125% atau layar kecil, tombol ekspor di bagian bawah sidebar terpotong/tidak kelihatan.
Ganti ke `CTkScrollableFrame` — isinya bisa di-scroll, semua tombol tetap bisa diakses.

Side effect: ada scrollbar kecil di sisi kanan sidebar yang muncul meski konten tidak penuh.
Belum ketemu cara hide scrollbar-nya di CustomTkinter tanpa hack kotor, jadi dibiarkan.
