import time
import re
import os
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

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
    """Fetch regency list dynamically from LPJK API."""
    if not provinsi_name or provinsi_name == "Nasional":
        return []
    try:
        url = f"https://lpjk.pu.go.id/laporan-lpjk/kabupaten/{provinsi_name}"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            return [k.get("nama_kabupaten_dagri") for k in data if k.get("nama_kabupaten_dagri")]
    except Exception:
        pass
    return []

def extract_contact_info(html_content, plain_text=""):
    """
    Extract WhatsApp/Mobile, Email, Telephone, Address, and PIC from detail HTML/Text.
    """
    combined_text = (plain_text + " " + (BeautifulSoup(html_content, "html.parser").get_text(" ") if html_content else "")).strip()

    # 1. Extract Emails
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    raw_emails = re.findall(email_pattern, combined_text)
    valid_emails = []
    for em in raw_emails:
        em_clean = em.strip().rstrip(".")
        if not re.search(r'\.(png|jpg|jpeg|gif|css|js|svg)$', em_clean, re.I) and em_clean not in valid_emails:
            valid_emails.append(em_clean)
    email_str = ", ".join(valid_emails) if valid_emails else ""

    # 2. Extract WhatsApp / Mobile Numbers (Indonesian 08xx / +628xx with valid operator prefixes)
    # Valid mobile prefixes: 0811-0819, 0821-0823, 0831-0838, 0851-0859, 0877-0878, 0881-0889, 0895-0899
    wa_pattern = r'(?:\+?62|0)8(?:1[1-9]|2[1-3]|3[1-38]|5[1-35-9]|7[78]|8[1-9]|9[5-9])[0-9\s\-]{6,9}[0-9]'
    raw_was = re.findall(wa_pattern, combined_text)
    clean_was = []
    wa_links = []
    for num in raw_was:
        digits = re.sub(r'[^\d]', '', num)
        if digits.startswith("08"):
            digits = "628" + digits[2:]
        elif digits.startswith("8"):
            digits = "62" + digits
        if digits.startswith("628") and 10 <= len(digits) <= 13:
            if digits not in clean_was:
                clean_was.append(digits)
                wa_links.append(f"https://wa.me/{digits}")

    wa_str = ", ".join(clean_was) if clean_was else ""
    wa_link_str = ", ".join(wa_links) if wa_links else ""

    # 3. Extract Landline / Fixed Telephone (Strict 9-11 digits to avoid transaction IDs)
    # Valid area codes e.g. 021, 022, 024, 031, 061, 0711, 0274, etc.
    phone_pattern = r'(?:\(0\d{2,4}\)|0\d{2,4})[\s\-]?[1-9]\d{5,7}'
    raw_phones = re.findall(phone_pattern, combined_text)
    clean_phones = []
    for ph in raw_phones:
        ph_clean = ph.strip()
        digits = re.sub(r'[^\d]', '', ph_clean)
        # Landline must be between 9 and 11 digits and not mobile
        if not digits.startswith("08") and not digits.startswith("628") and 9 <= len(digits) <= 11:
            if ph_clean not in clean_phones:
                clean_phones.append(ph_clean)
    phone_str = ", ".join(clean_phones) if clean_phones else ""

    # 4. Extract structured fields if table exists in HTML
    alamat = ""
    pimpinan = ""
    if html_content:
        soup = BeautifulSoup(html_content, "html.parser")
        for tr in soup.find_all("tr"):
            text_row = tr.get_text(" ", strip=True)
            if re.search(r'alamat|domisili', text_row, re.I):
                tds = tr.find_all(["td", "th"])
                if len(tds) >= 2:
                    alamat = tds[-1].get_text(" ", strip=True)
            if re.search(r'pimpinan|direktur|penanggung jawab|pjbu', text_row, re.I):
                tds = tr.find_all(["td", "th"])
                if len(tds) >= 2:
                    pimpinan = tds[-1].get_text(" ", strip=True)

    return {
        "email": email_str,
        "whatsapp": wa_str,
        "wa_link": wa_link_str,
        "telepon": phone_str,
        "alamat": alamat,
        "pimpinan": pimpinan
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
        """Initialize Chrome or Edge browser driver."""
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
                self.log(f"Error fatal browser: {e_edge}")
                return False

    def scrape(self, keyword="", jenis="nama", provinsi="", kabupaten="", kualifikasi="", max_pages=5, fetch_details=True, headless=False):
        """
        Execute scraping workflow.
        """
        self.is_running = True
        self.results = []
        total_wa = 0
        total_email = 0

        if not self.driver:
            if not self.start_browser(headless=headless):
                self.is_running = False
                return self.results

        try:
            self.log("Membuka website LPJK PUPR: https://lpjk.pu.go.id/laporan-lpjk/sebaran/cari ...")
            self.status_callback("Membuka portal LPJK...", 0.05, {"total": 0, "wa": 0, "email": 0})
            self.driver.get("https://lpjk.pu.go.id/laporan-lpjk/sebaran/cari")
            
            # Wait for search form to be ready
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.ID, "cari"))
            )
            time.sleep(1)

            # 1. Fill Form Filters
            self.log(f"Mengisi form filter (Kata Kunci: '{keyword or 'Semua'}', Provinsi: '{provinsi or 'Semua'}')...")
            if keyword:
                cari_input = self.driver.find_element(By.ID, "cari")
                cari_input.clear()
                cari_input.send_keys(keyword)

            if jenis == "npwp":
                try:
                    radio_npwp = self.driver.find_element(By.ID, "flexRadioDefault2")
                    radio_npwp.click()
                except Exception:
                    pass

            if provinsi:
                try:
                    select_prov = Select(self.driver.find_element(By.ID, "propinsi"))
                    select_prov.select_by_value(provinsi)
                    time.sleep(1.5)  # wait for kabupaten ajax
                except Exception as e:
                    self.log(f"Info provinsi: {e}")

            if kabupaten:
                try:
                    select_kab = Select(self.driver.find_element(By.ID, "kabupaten"))
                    select_kab.select_by_visible_text(kabupaten)
                except Exception as e:
                    self.log(f"Info kabupaten: {e}")

            if kualifikasi:
                try:
                    select_kual = Select(self.driver.find_element(By.ID, "kualifikasi"))
                    select_kual.select_by_value(kualifikasi)
                except Exception:
                    pass

            # 2. Try auto-clicking reCAPTCHA anchor
            try:
                iframe = self.driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha/api2/anchor']")
                if iframe:
                    self.driver.switch_to.frame(iframe[0])
                    chk = self.driver.find_element(By.ID, "recaptcha-anchor")
                    chk.click()
                    self.driver.switch_to.default_content()
                    self.log("Mencoba klik checkbox reCAPTCHA...")
                    time.sleep(1)
            except Exception:
                try:
                    self.driver.switch_to.default_content()
                except Exception:
                    pass

            self.log("=" * 50)
            self.log(">>> PERHATIAN: Silakan lihat jendela browser.")
            self.log(">>> Centang kotak reCAPTCHA (I'm not a robot), lalu klik tombol Search di browser!")
            self.log(">>> Aplikasi akan otomatis mengekstrak data begitu tabel hasil pencarian muncul.")
            self.log("=" * 50)
            self.status_callback("Menunggu penyelesaian reCAPTCHA & klik Search...", 0.15, {"total": 0, "wa": 0, "email": 0})

            # 3. Wait loop: Detect either reCAPTCHA solved & auto-submit, or wait for valid data rows
            data_found = False
            start_wait = time.time()
            max_wait_seconds = 240  # up to 4 minutes wait for user

            while self.is_running and (time.time() - start_wait < max_wait_seconds):
                # A. Check if reCAPTCHA solved, auto click submit if needed
                try:
                    token_el = self.driver.find_elements(By.ID, "g-recaptcha-response")
                    if token_el and len(token_el[0].get_attribute("value") or "") > 0:
                        if "searching" not in self.driver.current_url.lower():
                            self.log("reCAPTCHA terverifikasi! Mengirim pencarian otomatis...")
                            self.driver.execute_script("document.querySelector('form').submit();")
                            time.sleep(2)
                except Exception:
                    pass

                # B. Check if results table has actual data
                try:
                    trs = self.driver.find_elements(By.CSS_SELECTOR, "#TABLE_1 tbody tr")
                    if trs:
                        tds = trs[0].find_elements(By.TAG_NAME, "td")
                        first_text = trs[0].text.strip()
                        
                        if "No matching records found" in first_text:
                            self.log("Pencarian selesai: Tidak ada data perusahaan yang cocok dengan filter tersebut.")
                            self.status_callback("Tidak ada data yang cocok.", 1.0, {"total": 0, "wa": 0, "email": 0})
                            self.is_running = False
                            return self.results

                        if len(tds) >= 5 and "No data available" not in first_text and "Loading" not in first_text:
                            data_found = True
                            self.log(f"Hasil pencarian terdeteksi! Ditemukan data perusahaan: {trs[0].text[:60]}...")
                            break
                except Exception:
                    pass

                time.sleep(1)

            if not data_found:
                self.log("Waktu tunggu habis atau tidak ada data yang dimuat.")
                self.status_callback("Waktu tunggu habis.", 0.0, {"total": 0, "wa": 0, "email": 0})
                self.is_running = False
                return self.results

            # 4. Try setting DataTables to 100 entries per page for 10x faster scraping
            total_records_detected = 0
            try:
                length_el = self.driver.find_elements(By.NAME, "TABLE_1_length")
                if length_el:
                    sel = Select(length_el[0])
                    for val in ["100", "50", "25"]:
                        try:
                            sel.select_by_value(val)
                            self.log(f"Mengubah tampilan tabel menjadi {val} baris per halaman (scraping jauh lebih cepat)...")
                            time.sleep(2)
                            break
                        except Exception:
                            continue
            except Exception as e_len:
                self.log(f"Info set length tabel: {e_len}")

            # Parse total records from DataTables info (e.g. 'Showing 1 to 100 of 17,900 entries')
            try:
                info_el = self.driver.find_elements(By.ID, "TABLE_1_info")
                if info_el:
                    info_text = info_el[0].text
                    self.log(f"Info status LPJK: {info_text}")
                    match_total = re.search(r'of\s+([\d,\.]+)\s+entries', info_text, re.I)
                    if match_total:
                        total_records_detected = int(match_total.group(1).replace(",", "").replace(".", ""))
                        self.log(f">>> TERDETEKSI TOTAL {total_records_detected:,} DATA PERUSAHAAN DI LPJK! <<<")
            except Exception:
                pass

            # 5. Extract data across pages
            current_page = 1
            global_no = 1
            is_unlimited = (max_pages <= 0 or max_pages >= 9999)
            target_str = f"Semua Halaman (Target: {total_records_detected:,} data)" if is_unlimited else f"Maksimal {max_pages} Halaman"
            self.log(f"Target Scraping: {target_str}")

            while self.is_running:
                if not is_unlimited and current_page > max_pages:
                    self.log(f"Batas {max_pages} halaman tercapai.")
                    break

                total_display_info = f"/{total_records_detected:,}" if total_records_detected else ""
                self.log(f"--- Mengekstrak Halaman {current_page} (Total Saat Ini: {len(self.results)}{total_display_info}) ---")
                prog = 0.5 if is_unlimited else min(0.15 + (current_page / max(max_pages, 1)) * 0.8, 0.95)
                self.status_callback(
                    f"Halaman {current_page}: {len(self.results)}{total_display_info} data...",
                    prog,
                    {"total": len(self.results), "wa": total_wa, "email": total_email}
                )

                rows = self.driver.find_elements(By.CSS_SELECTOR, "#TABLE_1 tbody tr")
                self.log(f"Ditemukan {len(rows)} baris perusahaan di Halaman {current_page}.")

                for row_idx, row in enumerate(rows):
                    if not self.is_running:
                        self.log("Proses dihentikan oleh pengguna.")
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

                        contact_data = {
                            "email": "",
                            "whatsapp": "",
                            "wa_link": "",
                            "telepon": "",
                            "alamat": "",
                            "pimpinan": ""
                        }

                        # Fetch detail for WhatsApp & Email
                        if fetch_details:
                            try:
                                detail_html = ""
                                if detail_href:
                                    script = f"""
                                    var done = arguments[arguments.length - 1];
                                    $.ajax({{
                                        url: '{detail_href}',
                                        type: 'GET',
                                        timeout: 8000,
                                        success: function(data) {{ done(data); }},
                                        error: function() {{ done(''); }}
                                    }});
                                    """
                                    detail_html = self.driver.execute_async_script(script)

                                if not detail_html and detail_btn:
                                    self.driver.execute_script("arguments[0].click();", detail_btn)
                                    time.sleep(1)
                                    modal_body = self.driver.find_element(By.ID, "smallBody")
                                    detail_html = modal_body.get_attribute("innerHTML")
                                    close_btn = self.driver.find_element(By.CSS_SELECTOR, "#smallModal .close")
                                    self.driver.execute_script("arguments[0].click();", close_btn)

                                if detail_html:
                                    contact_data = extract_contact_info(detail_html)

                            except Exception:
                                pass

                        item = {
                            "no": global_no,
                            "nama": nama_bu,
                            "whatsapp": contact_data["whatsapp"],
                            "wa_link": contact_data["wa_link"],
                            "email": contact_data["email"],
                            "telepon": contact_data["telepon"],
                            "pimpinan": contact_data["pimpinan"],
                            "provinsi": prov,
                            "kabupaten": kab,
                            "npwp": npwp_val,
                            "kualifikasi": kualifikasi.upper() if kualifikasi else "-",
                            "alamat": contact_data["alamat"],
                            "subklas": ""
                        }

                        if contact_data["whatsapp"]:
                            total_wa += 1
                        if contact_data["email"]:
                            total_email += 1

                        self.results.append(item)
                        self.row_callback(item)
                        global_no += 1

                        # Periodic auto-save every 50 records
                        if len(self.results) % 50 == 0:
                            self.auto_save_checkpoint()

                        wa_log = f"WA: {contact_data['whatsapp']}" if contact_data['whatsapp'] else "WA: -"
                        em_log = f"Email: {contact_data['email']}" if contact_data['email'] else "Email: -"
                        self.log(f"[{global_no - 1}] {nama_bu} | {wa_log} | {em_log}")

                    except Exception as e_row:
                        self.log(f"Error parsing row {row_idx + 1}: {e_row}")

                # Update live counter
                self.status_callback(
                    f"Halaman {current_page} selesai. Total {len(self.results)}{total_display_info} data.", 
                    prog,
                    {"total": len(self.results), "wa": total_wa, "email": total_email}
                )

                # Check pagination next
                try:
                    next_btn = self.driver.find_element(By.ID, "TABLE_1_next")
                    btn_classes = next_btn.get_attribute("class") or ""
                    if "disabled" in btn_classes:
                        self.log("Halaman berikutnya tidak tersedia (halaman terakhir tercapai).")
                        break
                    
                    self.log(f"Pindah ke halaman {current_page + 1}...")
                    next_link = next_btn.find_element(By.TAG_NAME, "a")
                    self.driver.execute_script("arguments[0].click();", next_link)
                    time.sleep(2)
                    current_page += 1
                except Exception as e_page:
                    self.log(f"Selesai (tidak ada tombol halaman berikutnya): {e_page}")
                    break

            # Final auto-save
            self.auto_save_checkpoint()

            self.log("=" * 50)
            self.log(f"SCRAPING SELESAI! Total Data: {len(self.results)}, WhatsApp: {total_wa}, Email: {total_email}")
            self.log("File auto-save tersimpan di folder 'hasil_scraping'.")
            self.log("Silakan klik 'Ekspor ke Excel (.xlsx)' untuk menyimpan hasil.")
            self.log("=" * 50)
            self.status_callback(f"Selesai! {len(self.results)} data ({total_wa} WA, {total_email} Email)", 1.0, {
                "total": len(self.results), "wa": total_wa, "email": total_email
            })

        except Exception as e:
            self.log(f"Terjadi kesalahan saat scraping: {e}")
            self.status_callback(f"Error: {e}", 0.0, {"total": len(self.results), "wa": total_wa, "email": total_email})
        finally:
            self.is_running = False

        return self.results

    def auto_save_checkpoint(self):
        """Automatically save data checkpoint to disk so user never loses progress."""
        if not self.results:
            return
        try:
            from export import export_to_excel, export_to_csv
            out_dir = os.path.join(os.getcwd(), "hasil_scraping")
            os.makedirs(out_dir, exist_ok=True)
            export_to_excel(self.results, os.path.join(out_dir, "LPJK_AutoSave_Terbaru.xlsx"))
            export_to_csv(self.results, os.path.join(out_dir, "LPJK_AutoSave_Terbaru.csv"))
            self.log(f"💾 Checkpoint Auto-Save tersimpan ({len(self.results)} data)...")
        except Exception:
            pass

    def submit_search_now(self):
        """Helper to force submit the form in browser."""
        if self.driver:
            try:
                self.driver.execute_script("document.querySelector('form').submit();")
                self.log("Mengirim form pencarian...")
            except Exception as e:
                self.log(f"Gagal mengirim form: {e}")

    def stop(self):
        """Signal scraper to stop."""
        self.is_running = False
        self.log("Menghentikan scraper...")

    def close(self):
        """Close browser instance."""
        self.is_running = False
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
