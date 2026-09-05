import time
import re
import os
import random
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://lpjk.pu.go.id/laporan-lpjk/sebaran/cari"
KABUPATEN_API = "https://lpjk.pu.go.id/laporan-lpjk/kabupaten/{}"
AUTOSAVE_INTERVAL = 50
MAX_WAIT_SECONDS = 240

# Konfigurasi Concurrency (Serentak) & Anti-Rate Limit (HTTP 429)
BATCH_SIZE = 3               # Jumlah request detail serentak per batch (2-3)
BATCH_STAGGER_MS = 1500      # Jeda antar request dalam 1 batch (1.5 dtk) untuk mencegah burst spike
BATCH_INTERVAL_MIN = 4.0     # Jeda minimum antar batch (4.0 detik)
BATCH_INTERVAL_MAX = 5.5     # Jeda maksimum antar batch (5.5 detik)
PAGE_COOLDOWN_MIN = 10.0     # Micro-break jeda antar halaman (10 detik) untuk reset token bucket Nginx
PAGE_COOLDOWN_MAX = 12.0     # Micro-break jeda antar halaman (12 detik)
HTTP_429_COOLDOWN = 40       # Global pause (detik) saat server LPJK merespons 429

# Prefix operator seluler Indonesia yang valid (per 2024)
# Sengaja tidak pakai \d+ generik supaya nomor resi/sertifikat SBU tidak ikut tertangkap
MOBILE_PATTERN = r'(?:\+?62|0)8(?:1[1-9]|2[1-3]|3[1-38]|5[1-35-9]|7[78]|8[1-9]|9[5-9])[0-9\s\-]{6,9}[0-9]'

# Telepon kabel: kode area 2-4 digit + nomor pelanggan, total 9-11 digit
# Batas atas 11 digit penting — angka lebih panjang biasanya nomor dokumen, bukan telepon
LANDLINE_PATTERN = r'(?:\(0\d{2,4}\)|0\d{2,4})[\s\-]?[1-9]\d{5,7}'

EMAIL_PATTERN = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
EMAIL_IGNORE_EXT = re.compile(r'\.(png|jpg|jpeg|gif|css|js|svg)$', re.I)

PROVINSI_LIST = [
    "Nasional", "Aceh", "Sumatera Utara", "Sumatera Barat", "Riau", "Jambi",
    "Sumatera Selatan", "Bengkulu", "Lampung", "DKI Jakarta", "Jawa Barat",
    "Jawa Tengah", "DI Yogyakarta", "Jawa Timur", "Banten", "Bali",
    "Nusa Tenggara Barat", "Nusa Tenggara Timur", "Kalimantan Barat",
    "Kalimantan Tengah", "Kalimantan Selatan", "Kalimantan Timur",
    "Kalimantan Utara", "Sulawesi Utara", "Sulawesi Tengah", "Sulawesi Selatan",
    "Sulawesi Tenggara", "Gorontalo", "Sulawesi Barat", "Maluku",
    "Maluku Utara", "Papua Barat", "Papua", "Papua Selatan",
    "Papua Tengah", "Papua Pegunungan", "Papua Barat Daya"
]


def fetch_kabupaten(provinsi_name):
    if not provinsi_name or provinsi_name == "Nasional":
        return []
    try:
        res = requests.get(KABUPATEN_API.format(provinsi_name), timeout=10)
        if res.status_code == 200:
            return [k.get("nama_kabupaten_dagri") for k in res.json() if k.get("nama_kabupaten_dagri")]
    except requests.RequestException as e:
        pass
    return []


def normalize_mobile(raw_digits):
    if raw_digits.startswith("08"):
        return "628" + raw_digits[2:]
    if raw_digits.startswith("8"):
        return "62" + raw_digits
    return raw_digits


def extract_emails(text):
    results = []
    for em in re.findall(EMAIL_PATTERN, text):
        em = em.rstrip(".")
        if not EMAIL_IGNORE_EXT.search(em) and em not in results:
            results.append(em)
    return results


def extract_mobile_numbers(text):
    numbers = []
    links = []
    for raw in re.findall(MOBILE_PATTERN, text):
        digits = normalize_mobile(re.sub(r'[^\d]', '', raw))
        if digits.startswith("628") and 10 <= len(digits) <= 13 and digits not in numbers:
            numbers.append(digits)
            links.append(f"https://wa.me/{digits}")
    return numbers, links


def extract_landlines(text):
    results = []
    for raw in re.findall(LANDLINE_PATTERN, text):
        raw = raw.strip()
        digits = re.sub(r'[^\d]', '', raw)
        if not digits.startswith(("08", "628")) and 9 <= len(digits) <= 11 and raw not in results:
            results.append(raw)
    return results


def extract_table_fields(html):
    alamat = ""
    pimpinan = ""
    soup = BeautifulSoup(html, "html.parser")
    for tr in soup.find_all("tr"):
        row_text = tr.get_text(" ", strip=True)
        tds = tr.find_all(["td", "th"])
        if len(tds) < 2:
            continue
        last_val = tds[-1].get_text(" ", strip=True)
        if re.search(r'alamat|domisili', row_text, re.I):
            alamat = last_val
        elif re.search(r'pimpinan|direktur|penanggung jawab|pjbu', row_text, re.I):
            pimpinan = last_val
    return alamat, pimpinan


def extract_contact_info(html_content, plain_text=""):
    soup_text = BeautifulSoup(html_content, "html.parser").get_text(" ") if html_content else ""
    combined = (plain_text + " " + soup_text).strip()

    emails = extract_emails(combined)
    mobile_numbers, wa_links = extract_mobile_numbers(combined)
    landlines = extract_landlines(combined)

    alamat, pimpinan = ("", "")
    if html_content:
        alamat, pimpinan = extract_table_fields(html_content)

    return {
        "email": ", ".join(emails),
        "whatsapp": ", ".join(mobile_numbers),
        "wa_link": ", ".join(wa_links),
        "telepon": ", ".join(landlines),
        "alamat": alamat,
        "pimpinan": pimpinan,
    }


class LPJKScraper:
    def __init__(self, log_callback=None, status_callback=None, row_callback=None, update_row_callback=None):
        self.log_callback = log_callback or (lambda msg: None)
        self.status_callback = status_callback or (lambda txt, prog, metrics: None)
        self.row_callback = row_callback or (lambda row: None)
        # Dipanggil saat second pass berhasil update data baris yang sebelumnya ter-skip
        self.update_row_callback = update_row_callback or (lambda row: None)
        self.driver = None
        self.is_running = False
        self.results = []
        self.skipped_items = []  # Menyimpan item yang gagal di-fetch detail-nya

    def log(self, message):
        self.log_callback(message)

    def start_browser(self, headless=False):
        self.log("Membuka browser otomatis...")
        try:
            opts = ChromeOptions()
            if headless:
                opts.add_argument("--headless=new")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-features=Translate,OptimizationHints")
            opts.add_argument("--no-default-browser-check")
            opts.add_argument("--no-first-run")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            self.driver = webdriver.Chrome(options=opts)
            self.driver.set_script_timeout(35)
            self.driver.set_page_load_timeout(60)
            self.log("Browser Google Chrome berhasil dibuka.")
            return True
        except Exception as e_chrome:
            self.log(f"Chrome tidak tersedia ({e_chrome}), beralih ke Microsoft Edge...")
            try:
                e_opts = EdgeOptions()
                if headless:
                    e_opts.add_argument("--headless=new")
                e_opts.add_argument("--disable-gpu")
                e_opts.add_argument("--no-sandbox")
                e_opts.add_argument("--disable-dev-shm-usage")
                e_opts.add_argument("--disable-features=Translate,OptimizationHints")
                e_opts.add_argument("--no-default-browser-check")
                e_opts.add_argument("--no-first-run")
                self.driver = webdriver.Edge(options=e_opts)
                self.driver.set_script_timeout(35)
                self.driver.set_page_load_timeout(60)
                self.log("Browser Microsoft Edge berhasil dibuka.")
                return True
            except Exception as e_edge:
                self.log(f"Gagal membuka browser: {e_edge}")
                return False

    def _fill_form(self, keyword, jenis, provinsi, kabupaten, kualifikasi):
        if keyword:
            field = self.driver.find_element(By.ID, "cari")
            field.clear()
            field.send_keys(keyword)

        if jenis == "npwp":
            try:
                self.driver.find_element(By.ID, "flexRadioDefault2").click()
            except Exception as e:
                self.log(f"Gagal pilih radio NPWP: {e}")

        if provinsi:
            try:
                Select(self.driver.find_element(By.ID, "propinsi")).select_by_value(provinsi)
                time.sleep(1.5)  # tunggu AJAX kabupaten selesai load
            except Exception as e:
                self.log(f"Gagal pilih provinsi: {e}")

        if kabupaten:
            try:
                Select(self.driver.find_element(By.ID, "kabupaten")).select_by_visible_text(kabupaten)
            except Exception as e:
                self.log(f"Gagal pilih kabupaten: {e}")

        if kualifikasi:
            try:
                Select(self.driver.find_element(By.ID, "kualifikasi")).select_by_value(kualifikasi)
            except Exception as e:
                self.log(f"Gagal pilih kualifikasi: {e}")

    def _try_click_recaptcha(self):
        try:
            iframes = self.driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha/api2/anchor']")
            if iframes:
                self.driver.switch_to.frame(iframes[0])
                self.driver.find_element(By.ID, "recaptcha-anchor").click()
                self.driver.switch_to.default_content()
                self.log("Mencoba klik checkbox reCAPTCHA...")
                time.sleep(1)
        except Exception:
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass

    def _wait_for_results(self):
        start = time.time()
        while self.is_running and (time.time() - start < MAX_WAIT_SECONDS):
            try:
                # auto-submit kalau token captcha sudah terisi (user sudah centang)
                token_el = self.driver.find_elements(By.ID, "g-recaptcha-response")
                if token_el and len(token_el[0].get_attribute("value") or "") > 0:
                    if "searching" not in self.driver.current_url.lower():
                        self.log("reCAPTCHA terverifikasi! Mengirim pencarian otomatis...")
                        self.driver.execute_script("document.querySelector('form').submit();")
                        time.sleep(2)
            except Exception:
                pass

            try:
                rows = self.driver.find_elements(By.CSS_SELECTOR, "#TABLE_1 tbody tr")
                if rows:
                    first_text = rows[0].text.strip()
                    if "No matching records found" in first_text:
                        self.log("Tidak ada data yang cocok dengan filter.")
                        return "no_match"
                    tds = rows[0].find_elements(By.TAG_NAME, "td")
                    if len(tds) >= 5 and "No data available" not in first_text and "Loading" not in first_text:
                        return "found"
            except Exception:
                pass

            time.sleep(1)

        return "timeout"

    def _set_table_page_size(self):
        try:
            length_el = self.driver.find_elements(By.NAME, "TABLE_1_length")
            if length_el:
                sel = Select(length_el[0])
                # Gunakan 25 atau 50 baris per halaman agar tidak memicu rate-limit server LPJK
                for val in ["25", "50", "10"]:
                    try:
                        sel.select_by_value(val)
                        self.log(f"Tabel diset {val} baris per halaman untuk stabilitas request.")
                        time.sleep(2)
                        break
                    except Exception:
                        continue
        except Exception as e:
            self.log(f"Gagal mengubah ukuran tabel: {e}")

    def _detect_total_records(self):
        try:
            info_el = self.driver.find_elements(By.ID, "TABLE_1_info")
            if info_el:
                info_text = info_el[0].text
                self.log(f"Info DataTables: {info_text}")
                match = re.search(r'of\s+([\d,\.]+)\s+entries', info_text, re.I)
                if match:
                    total = int(match.group(1).replace(",", "").replace(".", ""))
                    self.log(f"Total data terdeteksi: {total:,}")
                    return total
        except Exception as e:
            self.log(f"Gagal membaca total data: {e}")
        return 0

    def _sleep_with_cancel(self, seconds):
        steps = int(seconds * 10)
        for _ in range(steps):
            if not self.is_running:
                return False
            time.sleep(0.1)
        return True

    def _wait_for_new_page(self, previous_first_text="", max_wait=20):
        """
        Menunggu secara aktif hingga DataTables selesai merender baris-baris halaman baru.
        Mencegah pembacaan data kosong atau stale element saat server LPJK merespons lambat.
        """
        start = time.time()
        while self.is_running and (time.time() - start < max_wait):
            try:
                # 1. Cek indikator processing DataTables
                processing_els = self.driver.find_elements(By.CSS_SELECTOR, ".dataTables_processing")
                if processing_els and processing_els[0].is_displayed():
                    time.sleep(0.4)
                    continue

                # 2. Cek baris tabel
                rows = self.driver.find_elements(By.CSS_SELECTOR, "#TABLE_1 tbody tr")
                if rows:
                    first_text = rows[0].text.strip()
                    if "Loading" in first_text or "Processing" in first_text:
                        time.sleep(0.4)
                        continue
                    if "No matching records found" in first_text or "No data available" in first_text:
                        return False, []

                    tds = rows[0].find_elements(By.TAG_NAME, "td")
                    if len(tds) >= 5:
                        # Jika ada teks pembanding baris pertama halaman sebelumnya, pastikan sudah berubah
                        if not previous_first_text or first_text != previous_first_text:
                            return True, rows
            except Exception:
                pass
            time.sleep(0.4)

        # Jika waktu tunggu habis, kembalikan baris apa adanya jika valid
        try:
            fallback_rows = self.driver.find_elements(By.CSS_SELECTOR, "#TABLE_1 tbody tr")
            if fallback_rows and len(fallback_rows[0].find_elements(By.TAG_NAME, "td")) >= 5:
                return True, fallback_rows
        except Exception:
            pass
        return False, []

    def _navigate_to_next_page(self, current_page, previous_first_text):
        """
        Navigasi ke halaman berikutnya dengan proteksi retry 3x, verifikasi rendering aktif,
        dan penanganan aman agar scraper tidak berhenti tiba-tiba di ratusan data.
        """
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            if not self.is_running:
                return "stopped"

            try:
                next_btns = self.driver.find_elements(By.ID, "TABLE_1_next")
                if not next_btns:
                    self.log(f"⚠️ Tombol Next tidak terdeteksi (percobaan {attempt}/{max_retries}). Menunggu...")
                    self._sleep_with_cancel(3)
                    continue

                next_btn = next_btns[0]
                btn_class = next_btn.get_attribute("class") or ""
                if "disabled" in btn_class:
                    self.log("Halaman terakhir tercapai (tombol Next disabled).")
                    return "last_page"

                # Cari elemen tautan <a> di dalam tombol Next
                link_els = next_btn.find_elements(By.TAG_NAME, "a")
                target_btn = link_els[0] if link_els else next_btn

                # Klik dengan execute_script agar terbebas dari halangan elemen overlay
                self.driver.execute_script("arguments[0].click();", target_btn)

                # Tunggu secara aktif hingga baris halaman baru benar-benar muncul
                loaded, _ = self._wait_for_new_page(previous_first_text=previous_first_text, max_wait=15)
                if loaded:
                    return "success"

                self.log(f"⏳ Halaman {current_page + 1} belum selesai memuat (percobaan {attempt}/{max_retries}). Menunggu...")
                self._sleep_with_cancel(3)

            except Exception as e:
                self.log(f"⚠️ Kendala navigasi ke halaman {current_page + 1} (percobaan {attempt}/{max_retries}): {e}")
                self._sleep_with_cancel(3)

        # Verifikasi terakhir apakah tombol Next memang sudah disabled
        try:
            next_btns = self.driver.find_elements(By.ID, "TABLE_1_next")
            if next_btns and "disabled" in (next_btns[0].get_attribute("class") or ""):
                self.log("Halaman terakhir terkonfirmasi.")
                return "last_page"
        except Exception:
            pass

        self.log(f"❌ Navigasi ke halaman {current_page + 1} gagal setelah {max_retries} kali percobaan.")
        return "failed"

    def _fallback_modal_single(self, detail_btn):
        """Fallback mengambil modal jika AJAX tidak berhasil."""
        if not detail_btn:
            return ""
        detail_html = ""
        try:
            self.driver.execute_script("if (typeof $ !== 'undefined' && $('#smallBody').length) { $('#smallBody').empty(); }")
            self.driver.execute_script("arguments[0].click();", detail_btn)

            for _ in range(15):
                if not self.is_running:
                    break
                time.sleep(0.2)
                try:
                    modal_body = self.driver.find_element(By.ID, "smallBody")
                    content = modal_body.get_attribute("innerHTML") or ""
                    if "429" in content or "Too Many Requests" in content:
                        self.log("⚠️ Terdeteksi HTTP 429 pada modal. Cooldown 20 detik...")
                        self._sleep_with_cancel(20)
                        break
                    if len(content.strip()) > 50:
                        detail_html = content
                        break
                except Exception:
                    pass

            try:
                close_btn = self.driver.find_element(By.CSS_SELECTOR, "#smallModal .close, #smallModal button[data-bs-dismiss='modal'], #smallModal button[data-dismiss='modal']")
                self.driver.execute_script("arguments[0].click();", close_btn)
            except Exception:
                pass
        except Exception as e:
            self.log(f"Gagal fetch detail via modal fallback: {e}")

        try:
            self.driver.execute_script("if (typeof $ !== 'undefined' && $('#smallBody').length) { $('#smallBody').empty(); }")
        except Exception:
            pass

        return detail_html

    def _fetch_batch_details(self, batch):
        """
        Mengambil detail kontak untuk sekelompok (batch 2-3) baris secara serentak
        dengan jeda bertingkat (staggered delay) untuk mencegah lonjakan request dan HTTP 429.
        """
        if not batch or not self.is_running:
            return

        # 1. Bersihkan buffer modal
        try:
            self.driver.execute_script("if (typeof $ !== 'undefined' && $('#smallBody').length) { $('#smallBody').empty(); }")
        except Exception:
            pass

        # 2. Siapkan payload request dengan staggered delay (offset)
        tasks_payload = []
        for i, entry in enumerate(batch):
            href = entry.get("detail_href")
            if href:
                tasks_payload.append({
                    "batch_idx": i,
                    "url": href,
                    "delay": i * BATCH_STAGGER_MS
                })

        batch_results = {}
        max_retries = 2

        for attempt in range(max_retries + 1):
            if not self.is_running or not tasks_payload:
                break

            try:
                script = """
                var done = arguments[arguments.length - 1];
                var tasks = arguments[0];
                if (typeof $ === 'undefined' || typeof $.ajax === 'undefined') {
                    done([]);
                    return;
                }
                var promises = tasks.map(function(t) {
                    return new Promise(function(resolve) {
                        setTimeout(function() {
                            $.ajax({
                                url: t.url,
                                type: 'GET',
                                timeout: 12000,
                                success: function(data) { resolve({ batch_idx: t.batch_idx, status: 200, html: data }); },
                                error: function(xhr) { resolve({ batch_idx: t.batch_idx, status: xhr.status || 0, html: '' }); }
                            });
                        }, t.delay);
                    });
                });
                Promise.all(promises).then(function(results) {
                    done(results);
                });
                """
                res = self.driver.execute_async_script(script, tasks_payload)
                if not isinstance(res, list):
                    res = []

                is_429 = any(r.get("status") == 429 for r in res)

                if is_429:
                    cooldown = HTTP_429_COOLDOWN * (attempt + 1)
                    self.log(f"⚠️ Server LPJK limit (HTTP 429). Mengaktifkan Global Pause selama {cooldown} detik...")
                    for remaining in range(cooldown, 0, -1):
                        if not self.is_running:
                            return
                        if remaining % 10 == 0 or remaining <= 5:
                            self.log(f"⏳ Cooldown 429: sisa {remaining} detik...")
                        time.sleep(1)
                    continue  # Coba lagi batch yang sama

                # Catat hasil yang sukses
                for r in res:
                    idx = r.get("batch_idx")
                    status = r.get("status", 0)
                    html = r.get("html", "")
                    if status == 200 and html and len(html.strip()) > 50:
                        batch_results[idx] = html

                # Jika semua yang punya URL sudah berhasil, selesai
                needed_indices = {t["batch_idx"] for t in tasks_payload}
                if needed_indices.issubset(batch_results.keys()):
                    break

                # Jika ada yang gagal dan bukan 429, retry yang belum berhasil saja
                missing_indices = needed_indices - batch_results.keys()
                if attempt < max_retries and missing_indices:
                    cooldown_retry = 5 * (attempt + 1)
                    self.log(f"↩️ Retry {len(missing_indices)} detail yang belum terambil dalam {cooldown_retry} detik...")
                    if not self._sleep_with_cancel(cooldown_retry):
                        return
                    tasks_payload = [t for t in tasks_payload if t["batch_idx"] in missing_indices]
                else:
                    break

            except Exception as e:
                err_str = str(e).lower()
                if "timeout" in err_str:
                    self.log(f"⚠️ Server LPJK lambat/timeout sesaat ({e}). Cooldown 10 detik sebelum coba lagi...")
                    if not self._sleep_with_cancel(10):
                        return
                    continue
                self.log(f"Gagal execute batch AJAX: {e}")
                break

        # 3. Proses hasil untuk setiap item di dalam batch
        for i, entry in enumerate(batch):
            if not self.is_running:
                break

            item = entry["item"]
            detail_btn = entry.get("detail_btn")
            nama_bu = item["nama"]
            html_content = batch_results.get(i, "")

            # Fallback ke modal jika AJAX tidak membuahkan hasil
            if not html_content and detail_btn:
                self.log(f"  Mencoba fallback modal untuk '{nama_bu}'...")
                html_content = self._fallback_modal_single(detail_btn)

            if html_content:
                contact = extract_contact_info(html_content)
                item.update({
                    "whatsapp": contact["whatsapp"],
                    "wa_link": contact["wa_link"],
                    "email": contact["email"],
                    "telepon": contact["telepon"],
                    "pimpinan": contact["pimpinan"],
                    "alamat": contact["alamat"],
                })
                self.update_row_callback(item)

                wa_log = contact["whatsapp"] or "-"
                em_log = contact["email"] or "-"
                if contact["whatsapp"] or contact["email"] or contact["telepon"]:
                    self.log(f"[{item['no']}] {nama_bu} | WA: {wa_log} | Email: {em_log}")
                else:
                    extra_alamat = f" (Alamat: {contact['alamat'][:35]}...)" if contact['alamat'] else ""
                    self.log(f"[{item['no']}] {nama_bu} | Detail dimuat (Kontak tidak dicantumkan di LPJK){extra_alamat}")
            else:
                self.skipped_items.append({"item": item, "tds_idx": item["no"] - 1})
                self.log(f"[{item['no']}] ⚠️ {nama_bu} | Gagal memuat detail — ditandai untuk second pass")

    def _extract_rows(self, fetch_details, total_records):
        global_no = len(self.results) + 1
        current_page = 1
        is_unlimited = total_records <= 0
        total_display = f"/{total_records:,}" if total_records else ""

        while self.is_running:
            total_wa = sum(1 for r in self.results if r.get("whatsapp"))
            total_email = sum(1 for r in self.results if r.get("email"))

            self.log(f"--- Halaman {current_page} (dikumpulkan: {len(self.results)}{total_display}) ---")
            prog = 0.5 if is_unlimited else min(0.15 + (current_page / max(current_page + 5, 1)) * 0.8, 0.95)
            self.status_callback(
                f"Halaman {current_page}: {len(self.results)}{total_display} data...",
                prog,
                {"total": len(self.results), "wa": total_wa, "email": total_email}
            )

            # Tunggu secara aktif hingga baris halaman ter-render (menghindari tabel blank/processing)
            loaded, rows = self._wait_for_new_page(max_wait=15)
            if not loaded or not rows:
                self.log(f"Tidak ada data terdeteksi di halaman {current_page}.")
                break

            self.log(f"Ditemukan {len(rows)} baris di halaman {current_page}.")
            current_first_text = rows[0].text.strip() if rows else ""

            page_items = []

            # 1. Ekstrak data dasar seluruh baris di halaman ini terlebih dahulu
            for row_idx, row in enumerate(rows):
                if not self.is_running:
                    break
                try:
                    tds = row.find_elements(By.TAG_NAME, "td")
                    if len(tds) < 5:
                        continue

                    nama_bu = tds[1].text.strip()
                    prov = tds[2].text.strip()
                    kab = tds[3].text.strip()
                    npwp_val = tds[4].text.strip()

                    detail_href = ""
                    detail_btn = None
                    if len(tds) >= 6:
                        try:
                            detail_btn = tds[5].find_element(By.CSS_SELECTOR, "#smallButton, a[data-attr]")
                            detail_href = detail_btn.get_attribute("data-attr") or ""
                        except Exception:
                            pass

                    item = {
                        "no": global_no,
                        "nama": nama_bu,
                        "whatsapp": "",
                        "wa_link": "",
                        "email": "",
                        "telepon": "",
                        "pimpinan": "",
                        "provinsi": prov,
                        "kabupaten": kab,
                        "npwp": npwp_val,
                        "kualifikasi": "-",
                        "alamat": "",
                        "subklas": ""
                    }

                    self.results.append(item)
                    # Tampilkan baris seketika ke tabel antarmuka GUI!
                    self.row_callback(item)
                    global_no += 1

                    page_items.append({
                        "item": item,
                        "detail_href": detail_href,
                        "detail_btn": detail_btn
                    })

                    if not fetch_details:
                        self.log(f"[{item['no']}] {nama_bu}")

                except Exception as e:
                    self.log(f"Error parsing baris {row_idx + 1}: {e}")

            # 2. Ambil detail secara serentak (paralel batch 2-3 baris) dengan jeda acak 4-5 detik
            if fetch_details and page_items:
                total_batches = (len(page_items) + BATCH_SIZE - 1) // BATCH_SIZE
                for b_idx in range(total_batches):
                    if not self.is_running:
                        break

                    b_start = b_idx * BATCH_SIZE
                    batch = page_items[b_start:b_start + BATCH_SIZE]
                    self.log(f"Memproses batch detail {b_idx + 1}/{total_batches} ({len(batch)} perusahaan serentak)...")

                    self._fetch_batch_details(batch)

                    # Update metrik kontak real-time di antarmuka GUI
                    total_wa = sum(1 for r in self.results if r.get("whatsapp"))
                    total_email = sum(1 for r in self.results if r.get("email"))
                    self.status_callback(
                        f"Halaman {current_page}: {len(self.results)}{total_display} data...",
                        prog,
                        {"total": len(self.results), "wa": total_wa, "email": total_email}
                    )

                    if len(self.results) % AUTOSAVE_INTERVAL == 0:
                        self._auto_save()

                    # Jeda acak 4.0 - 5.5 detik antar-batch agar server tidak mendeteksi pola konstan
                    if b_idx + 1 < total_batches:
                        batch_delay = random.uniform(BATCH_INTERVAL_MIN, BATCH_INTERVAL_MAX)
                        if not self._sleep_with_cancel(batch_delay):
                            break

            total_wa = sum(1 for r in self.results if r.get("whatsapp"))
            total_email = sum(1 for r in self.results if r.get("email"))

            self.status_callback(
                f"Halaman {current_page} selesai. Total: {len(self.results)}{total_display}",
                prog,
                {"total": len(self.results), "wa": total_wa, "email": total_email}
            )

            # 3. Navigasi ke halaman berikutnya dengan Micro-Cooldown & Robust Retry
            if fetch_details and self.is_running:
                page_break = random.uniform(PAGE_COOLDOWN_MIN, PAGE_COOLDOWN_MAX)
                self.log(f"☕ Istirahat {page_break:.1f} detik antar-halaman untuk me-reset kuota limit server LPJK...")
                if not self._sleep_with_cancel(page_break):
                    break

            nav_status = self._navigate_to_next_page(current_page, current_first_text)
            if nav_status == "last_page":
                break
            elif nav_status in ("stopped", "failed"):
                break
            elif nav_status == "success":
                current_page += 1

        return total_wa, total_email

    def _second_pass(self):
        """Memproses ulang baris yang sebelumnya gagal di-fetch detail-nya."""
        if not self.skipped_items:
            return

        total_skipped = len(self.skipped_items)
        self.log("-" * 50)
        self.log(f"🔄 Second Pass: Memproses ulang {total_skipped} baris yang ter-skip...")
        self.log("-" * 50)
        self.status_callback(
            f"Second Pass: Memproses ulang {total_skipped} data yang ter-skip...",
            0.95,
            {"total": len(self.results), "wa": sum(1 for r in self.results if r.get('whatsapp')), "email": sum(1 for r in self.results if r.get('email'))}
        )

        recovered = 0
        batch_size = 2  # Pada second pass gunakan batch 2 agar lebih santai
        total_batches = (total_skipped + batch_size - 1) // batch_size

        for b_idx in range(total_batches):
            if not self.is_running:
                break

            b_start = b_idx * batch_size
            chunk = self.skipped_items[b_start:b_start + batch_size]
            batch_for_fetch = []
            for skip_info in chunk:
                item = skip_info["item"]
                detail_url = f"https://lpjk.pu.go.id/laporan-lpjk/sebaran/detail/{item.get('npwp', '')}"
                batch_for_fetch.append({
                    "item": item,
                    "detail_href": detail_url,
                    "detail_btn": None
                })

            self._fetch_batch_details(batch_for_fetch)

            for skip_info in chunk:
                item = skip_info["item"]
                if item.get("whatsapp") or item.get("email") or item.get("alamat"):
                    recovered += 1

            if b_idx + 1 < total_batches:
                self._sleep_with_cancel(random.uniform(BATCH_INTERVAL_MIN, BATCH_INTERVAL_MAX))

        self.skipped_items = []
        self.log("-" * 50)
        self.log(f"🔄 Second Pass selesai. {recovered}/{total_skipped} data berhasil dipulihkan.")
        self.log("-" * 50)


    def scrape(self, keyword="", jenis="nama", provinsi="", kabupaten="", kualifikasi="",
               max_pages=0, fetch_details=True, headless=False):
        self.is_running = True
        self.results = []

        if not self.driver:
            if not self.start_browser(headless=headless):
                self.is_running = False
                return self.results

        try:
            self.log(f"Membuka {BASE_URL} ...")
            self.status_callback("Membuka portal LPJK...", 0.05, {"total": 0, "wa": 0, "email": 0})
            self.driver.get(BASE_URL)

            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.ID, "cari"))
            )
            time.sleep(1)

            self.log(f"Mengisi form (keyword='{keyword or 'semua'}', provinsi='{provinsi or 'semua'}')...")
            self._fill_form(keyword, jenis, provinsi, kabupaten, kualifikasi)
            self._try_click_recaptcha()

            self.log("-" * 50)
            self.log("Centang reCAPTCHA di browser, lalu klik tombol Search.")
            self.log("Aplikasi akan otomatis lanjut setelah data muncul.")
            self.log("-" * 50)
            self.status_callback("Menunggu reCAPTCHA & klik Search...", 0.15, {"total": 0, "wa": 0, "email": 0})

            result = self._wait_for_results()

            if result == "no_match":
                self.status_callback("Tidak ada data yang cocok.", 1.0, {"total": 0, "wa": 0, "email": 0})
                self.is_running = False
                return self.results

            if result == "timeout":
                self.log("Waktu tunggu habis.")
                self.status_callback("Waktu tunggu habis.", 0.0, {"total": 0, "wa": 0, "email": 0})
                self.is_running = False
                return self.results

            self._set_table_page_size()
            total_records = self._detect_total_records()

            self.skipped_items = []
            total_wa, total_email = self._extract_rows(fetch_details, total_records)

            # Second pass: proses ulang semua baris yang ter-skip
            if fetch_details and self.skipped_items and self.is_running:
                self._second_pass()
                # Hitung ulang total WA & Email setelah second pass
                total_wa = sum(1 for r in self.results if r.get("whatsapp"))
                total_email = sum(1 for r in self.results if r.get("email"))

            self._auto_save()

            self.log("-" * 50)
            self.log(f"Selesai. Total: {len(self.results)}, WA: {total_wa}, Email: {total_email}")
            self.log("Data tersimpan di folder 'hasil_scraping'.")
            self.log("-" * 50)
            self.status_callback(
                f"Selesai! {len(self.results)} data ({total_wa} WA, {total_email} Email)",
                1.0,
                {"total": len(self.results), "wa": total_wa, "email": total_email}
            )

        except Exception as e:
            self.log(f"Error tidak terduga saat scraping: {e}")
            self.status_callback(f"Error: {e}", 0.0, {"total": len(self.results), "wa": 0, "email": 0})
        finally:
            self.is_running = False

        return self.results

    def _auto_save(self):
        if not self.results:
            return
        try:
            from export import export_to_excel, export_to_csv
            out_dir = os.path.join(os.getcwd(), "hasil_scraping")
            os.makedirs(out_dir, exist_ok=True)
            export_to_excel(self.results, os.path.join(out_dir, "LPJK_AutoSave_Terbaru.xlsx"))
            export_to_csv(self.results, os.path.join(out_dir, "LPJK_AutoSave_Terbaru.csv"))
            self.log(f"Auto-save: {len(self.results)} data tersimpan.")
        except Exception as e:
            self.log(f"Gagal auto-save: {e}")

    def submit_search_now(self):
        if self.driver:
            try:
                self.driver.execute_script("document.querySelector('form').submit();")
                self.log("Form pencarian dikirim.")
            except Exception as e:
                self.log(f"Gagal kirim form: {e}")

    def stop(self):
        self.is_running = False
        self.log("Scraper dihentikan.")

    def close(self):
        self.is_running = False
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                self.log(f"Gagal menutup browser: {e}")
            self.driver = None
