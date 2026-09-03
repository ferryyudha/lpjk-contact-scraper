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
    def __init__(self, log_callback=None, status_callback=None, row_callback=None):
        self.log_callback = log_callback or (lambda msg: None)
        self.status_callback = status_callback or (lambda txt, prog, metrics: None)
        self.row_callback = row_callback or (lambda row: None)
        self.driver = None
        self.is_running = False
        self.results = []

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
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            self.driver = webdriver.Chrome(options=opts)
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
                self.driver = webdriver.Edge(options=e_opts)
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

    def _fetch_row_detail(self, tds, company_name=""):
        detail_href = ""
        detail_btn = None
        if len(tds) >= 6:
            try:
                detail_btn = tds[5].find_element(By.CSS_SELECTOR, "#smallButton, a[data-attr]")
                detail_href = detail_btn.get_attribute("data-attr") or ""
            except Exception:
                pass

        detail_html = ""
        is_success = False

        # 1. Bersihkan buffer modal terlebih dahulu agar data perusahaan sebelumnya tidak tertinggal
        try:
            self.driver.execute_script("if (typeof $ !== 'undefined' && $('#smallBody').length) { $('#smallBody').empty(); }")
        except Exception:
            pass

        if detail_href:
            max_retries = 3
            for attempt in range(max_retries):
                if not self.is_running:
                    return "", False
                try:
                    script = f"""
                    var done = arguments[arguments.length - 1];
                    $.ajax({{
                        url: '{detail_href}',
                        type: 'GET',
                        timeout: 10000,
                        success: function(data) {{ done({{ status: 200, html: data }}); }},
                        error: function(xhr) {{ done({{ status: xhr.status || 0, html: '' }}); }}
                    }});
                    """
                    res = self.driver.execute_async_script(script)
                    status = res.get("status", 0) if isinstance(res, dict) else 200
                    html_content = res.get("html", "") if isinstance(res, dict) else (res or "")

                    if status == 429:
                        wait_sec = 15 * (attempt + 1)
                        self.log(f"⚠️ Server LPJK limit (HTTP 429). Cooldown {wait_sec} detik sebelum retry...")
                        for _ in range(wait_sec):
                            if not self.is_running:
                                return "", False
                            time.sleep(1)
                        continue
                    elif status == 200 and html_content:
                        detail_html = html_content
                        is_success = True
                        break
                    else:
                        break
                except Exception as e:
                    self.log(f"Gagal fetch detail via AJAX: {e}")
                    break

        # 2. Fallback modal jika AJAX tidak berhasil
        if not detail_html and detail_btn:
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
                            self.log("⚠️ Terdeteksi HTTP 429 pada modal. Cooldown 15 detik...")
                            time.sleep(15)
                            break
                        if len(content.strip()) > 50:
                            detail_html = content
                            is_success = True
                            break
                    except Exception:
                        pass

                try:
                    close_btn = self.driver.find_element(By.CSS_SELECTOR, "#smallModal .close, #smallModal button[data-bs-dismiss='modal'], #smallModal button[data-dismiss='modal']")
                    self.driver.execute_script("arguments[0].click();", close_btn)
                except Exception:
                    pass
            except Exception as e:
                self.log(f"Gagal fetch detail via modal: {e}")

        # Pastikan buffer modal dibersihkan kembali
        try:
            self.driver.execute_script("if (typeof $ !== 'undefined' && $('#smallBody').length) { $('#smallBody').empty(); }")
        except Exception:
            pass

        return detail_html, is_success

    def _extract_rows(self, fetch_details, total_records):
        global_no = len(self.results) + 1
        total_wa = sum(1 for r in self.results if r.get("whatsapp"))
        total_email = sum(1 for r in self.results if r.get("email"))
        current_page = 1
        is_unlimited = total_records <= 0

        total_display = f"/{total_records:,}" if total_records else ""

        while self.is_running:
            self.log(f"--- Halaman {current_page} (dikumpulkan: {len(self.results)}{total_display}) ---")
            prog = 0.5 if is_unlimited else min(0.15 + (current_page / max(current_page + 5, 1)) * 0.8, 0.95)
            self.status_callback(
                f"Halaman {current_page}: {len(self.results)}{total_display} data...",
                prog,
                {"total": len(self.results), "wa": total_wa, "email": total_email}
            )

            rows = self.driver.find_elements(By.CSS_SELECTOR, "#TABLE_1 tbody tr")
            self.log(f"Ditemukan {len(rows)} baris di halaman {current_page}.")

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

                    contact = {
                        "email": "", "whatsapp": "", "wa_link": "",
                        "telepon": "", "alamat": "", "pimpinan": ""
                    }

                    detail_success = False
                    if fetch_details:
                        detail_html, detail_success = self._fetch_row_detail(tds, company_name=nama_bu)
                        if detail_html:
                            contact = extract_contact_info(detail_html)

                        # Jeda dinamis 1.5 - 2.5 detik per baris untuk mencegah pemicu HTTP 429
                        time.sleep(random.uniform(1.5, 2.5))

                    item = {
                        "no": global_no,
                        "nama": nama_bu,
                        "whatsapp": contact["whatsapp"],
                        "wa_link": contact["wa_link"],
                        "email": contact["email"],
                        "telepon": contact["telepon"],
                        "pimpinan": contact["pimpinan"],
                        "provinsi": prov,
                        "kabupaten": kab,
                        "npwp": npwp_val,
                        "kualifikasi": "-",
                        "alamat": contact["alamat"],
                        "subklas": ""
                    }

                    if contact["whatsapp"]:
                        total_wa += 1
                    if contact["email"]:
                        total_email += 1

                    self.results.append(item)
                    self.row_callback(item)
                    global_no += 1

                    if len(self.results) % AUTOSAVE_INTERVAL == 0:
                        self._auto_save()

                    wa_log = contact["whatsapp"] or "-"
                    em_log = contact["email"] or "-"

                    if not fetch_details:
                        self.log(f"[{global_no - 1}] {nama_bu}")
                    elif contact["whatsapp"] or contact["email"] or contact["telepon"]:
                        self.log(f"[{global_no - 1}] {nama_bu} | WA: {wa_log} | Email: {em_log}")
                    elif detail_success:
                        extra_alamat = f" (Alamat: {contact['alamat'][:35]}...)" if contact['alamat'] else ""
                        self.log(f"[{global_no - 1}] {nama_bu} | Detail dimuat (Kontak tidak dicantumkan di LPJK){extra_alamat}")
                    else:
                        self.log(f"[{global_no - 1}] ⚠️ {nama_bu} | Gagal memuat detail (Server LPJK timeout/skip)")

                except Exception as e:
                    self.log(f"Error parsing baris {row_idx + 1}: {e}")

            self.status_callback(
                f"Halaman {current_page} selesai. Total: {len(self.results)}{total_display}",
                prog,
                {"total": len(self.results), "wa": total_wa, "email": total_email}
            )

            try:
                next_btn = self.driver.find_element(By.ID, "TABLE_1_next")
                if "disabled" in (next_btn.get_attribute("class") or ""):
                    self.log("Halaman terakhir tercapai.")
                    break
                self.driver.execute_script("arguments[0].click();", next_btn.find_element(By.TAG_NAME, "a"))
                time.sleep(2)
                current_page += 1
            except Exception as e:
                self.log(f"Navigasi halaman berikutnya gagal: {e}")
                break

        return total_wa, total_email

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

            total_wa, total_email = self._extract_rows(fetch_details, total_records)

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
