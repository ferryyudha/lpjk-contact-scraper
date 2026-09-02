import os
import sys
import threading
import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk

from scraper import LPJKScraper, PROVINSI_LIST, fetch_kabupaten
from export import export_to_excel, export_to_csv, export_to_json

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class LPJKScraperApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("LPJK PUPR Contact Scraper - WhatsApp & Email Extractor")
        self.geometry("1280x820")
        self.minsize(1080, 700)

        self.scraper = None
        self.scraped_data = []
        self.is_scraping = False

        self.init_layout()

    def init_layout(self):
        # Configure grid 1x2 (Sidebar & Main content)
        self.grid_columnconfigure(0, weight=0, minsize=370)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ==========================================
        # LEFT SIDEBAR (FILTERS & CONTROLS)
        # ==========================================
        self.sidebar_frame = ctk.CTkScrollableFrame(self, corner_radius=0, width=360)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar_frame.grid_columnconfigure(0, weight=1)

        # App Brand Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="⚡ LPJK CONTACT SCRAPER",
            font=ctk.CTkFont(size=17, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=14, pady=(16, 2), sticky="w")

        self.sublogo_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="Ekstraksi WhatsApp & Email Kontraktor LPJK",
            font=ctk.CTkFont(size=11),
            text_color="#94A3B8"
        )
        self.sublogo_label.grid(row=1, column=0, padx=14, pady=(0, 10), sticky="w")

        # 1. Search Keyword
        self.lbl_cari = ctk.CTkLabel(self.sidebar_frame, text="Kata Kunci Perusahaan:", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_cari.grid(row=2, column=0, padx=14, pady=(4, 2), sticky="w")

        self.entry_keyword = ctk.CTkEntry(self.sidebar_frame, placeholder_text="Kosongkan jika ingin ambil SEMUA", height=32)
        self.entry_keyword.grid(row=3, column=0, padx=14, pady=(0, 8), sticky="ew")

        # 2. Search Type Radio (Nama / NPWP)
        self.jenis_var = tk.StringVar(value="nama")
        self.radio_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.radio_frame.grid(row=4, column=0, padx=14, pady=(0, 6), sticky="w")

        self.rb_nama = ctk.CTkRadioButton(self.radio_frame, text="Nama Badan Usaha", variable=self.jenis_var, value="nama", font=ctk.CTkFont(size=11))
        self.rb_nama.pack(side="left", padx=(0, 10))

        self.rb_npwp = ctk.CTkRadioButton(self.radio_frame, text="NPWP", variable=self.jenis_var, value="npwp", font=ctk.CTkFont(size=11))
        self.rb_npwp.pack(side="left")

        # 3. Provinsi Dropdown
        self.lbl_prov = ctk.CTkLabel(self.sidebar_frame, text="Provinsi:", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_prov.grid(row=5, column=0, padx=14, pady=(4, 2), sticky="w")

        self.cb_provinsi = ctk.CTkComboBox(
            self.sidebar_frame,
            values=["Semua Provinsi"] + PROVINSI_LIST,
            command=self.on_provinsi_change,
            height=30
        )
        self.cb_provinsi.set("Semua Provinsi")
        self.cb_provinsi.grid(row=6, column=0, padx=14, pady=(0, 6), sticky="ew")

        # 4. Kabupaten Dropdown
        self.lbl_kab = ctk.CTkLabel(self.sidebar_frame, text="Kabupaten / Kota:", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_kab.grid(row=7, column=0, padx=14, pady=(4, 2), sticky="w")

        self.cb_kabupaten = ctk.CTkComboBox(self.sidebar_frame, values=["Semua Kabupaten"], height=30)
        self.cb_kabupaten.set("Semua Kabupaten")
        self.cb_kabupaten.grid(row=8, column=0, padx=14, pady=(0, 6), sticky="ew")

        # 5. Kualifikasi Dropdown
        self.lbl_kual = ctk.CTkLabel(self.sidebar_frame, text="Kualifikasi:", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_kual.grid(row=9, column=0, padx=14, pady=(4, 2), sticky="w")

        self.kual_map = {
            "Semua Kualifikasi": "",
            "Besar (B)": "b",
            "Menengah (M)": "m",
            "Kecil (K)": "k",
            "Spesial (S)": "s"
        }
        self.cb_kualifikasi = ctk.CTkComboBox(self.sidebar_frame, values=list(self.kual_map.keys()), height=30)
        self.cb_kualifikasi.set("Semua Kualifikasi")
        self.cb_kualifikasi.grid(row=10, column=0, padx=14, pady=(0, 8), sticky="ew")

        # 6. Target Scraping / Pagination Limit
        self.lbl_target = ctk.CTkLabel(self.sidebar_frame, text="Target Data / Batasan Halaman:", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_target.grid(row=11, column=0, padx=14, pady=(4, 2), sticky="w")

        self.chk_all_pages = ctk.CTkCheckBox(
            self.sidebar_frame,
            text="🔥 Ambil SEMUA Data (Tanpa Batas)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#38BDF8",
            command=self.toggle_all_pages
        )
        self.chk_all_pages.select()
        self.chk_all_pages.grid(row=12, column=0, padx=14, pady=(0, 6), sticky="w")

        self.page_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.page_frame.grid(row=13, column=0, padx=14, pady=(0, 8), sticky="ew")

        self.lbl_pages = ctk.CTkLabel(self.page_frame, text="Atau batasi (Halaman):", font=ctk.CTkFont(size=11), text_color="#94A3B8")
        self.lbl_pages.pack(side="left")

        self.entry_pages = ctk.CTkEntry(self.page_frame, width=60, height=28, state="disabled")
        self.entry_pages.insert(0, "50")
        self.entry_pages.pack(side="right")

        # 7. Switches
        self.switch_details = ctk.CTkSwitch(self.sidebar_frame, text="Ambil Kontak (WA & Email)", font=ctk.CTkFont(size=12))
        self.switch_details.select()
        self.switch_details.grid(row=14, column=0, padx=14, pady=(4, 4), sticky="w")

        self.switch_browser = ctk.CTkSwitch(self.sidebar_frame, text="Tampilkan Browser (Captcha)", font=ctk.CTkFont(size=12))
        self.switch_browser.select()
        self.switch_browser.grid(row=15, column=0, padx=14, pady=(0, 10), sticky="w")

        # 8. Action Buttons
        self.btn_start = ctk.CTkButton(
            self.sidebar_frame,
            text="🚀 MULAI SCRAPING",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#10B981",
            hover_color="#059669",
            height=38,
            command=self.start_scraping_thread
        )
        self.btn_start.grid(row=16, column=0, padx=14, pady=(2, 4), sticky="ew")

        self.btn_submit_now = ctk.CTkButton(
            self.sidebar_frame,
            text="🔍 Kirim Pencarian Sekarang",
            font=ctk.CTkFont(size=12),
            fg_color="#0284C7",
            hover_color="#0369A1",
            height=30,
            command=self.submit_search_now,
            state="disabled"
        )
        self.btn_submit_now.grid(row=17, column=0, padx=14, pady=(0, 4), sticky="ew")

        self.btn_stop = ctk.CTkButton(
            self.sidebar_frame,
            text="⏹ BERHENTI (Data Tersimpan)",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#EF4444",
            hover_color="#DC2626",
            height=32,
            command=self.stop_scraping,
            state="disabled"
        )
        self.btn_stop.grid(row=18, column=0, padx=14, pady=(0, 10), sticky="ew")

        # Export Buttons
        self.btn_export_excel = ctk.CTkButton(
            self.sidebar_frame,
            text="📊 Ekspor ke Excel (.xlsx)",
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            height=32,
            command=self.export_excel
        )
        self.btn_export_excel.grid(row=19, column=0, padx=14, pady=(2, 4), sticky="ew")

        self.btn_export_csv = ctk.CTkButton(
            self.sidebar_frame,
            text="📄 Ekspor ke CSV (.csv)",
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            height=32,
            command=self.export_csv
        )
        self.btn_export_csv.grid(row=20, column=0, padx=14, pady=(0, 4), sticky="ew")

        self.btn_open_folder = ctk.CTkButton(
            self.sidebar_frame,
            text="📂 Buka Folder Hasil (Auto-Save)",
            fg_color="#475569",
            hover_color="#334155",
            height=30,
            command=self.open_output_folder
        )
        self.btn_open_folder.grid(row=21, column=0, padx=14, pady=(0, 12), sticky="ew")

        # ==========================================
        # RIGHT MAIN AREA (METRICS, TABLE, LOGS)
        # ==========================================
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(3, weight=1)
        self.main_frame.grid_rowconfigure(5, weight=0)

        # --- Metrics Row ---
        self.metrics_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.metrics_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.metrics_frame.grid_columnconfigure((0, 1, 2), weight=1)

        # Metric 1: Total Data
        self.card_total = ctk.CTkFrame(self.metrics_frame, corner_radius=10, fg_color="#1E293B")
        self.card_total.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.lbl_card_total_title = ctk.CTkLabel(self.card_total, text="TOTAL PERUSAHAAN", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94A3B8")
        self.lbl_card_total_title.pack(anchor="w", padx=15, pady=(10, 0))
        self.lbl_card_total_val = ctk.CTkLabel(self.card_total, text="0", font=ctk.CTkFont(size=26, weight="bold"), text_color="#38BDF8")
        self.lbl_card_total_val.pack(anchor="w", padx=15, pady=(0, 10))

        # Metric 2: WhatsApp
        self.card_wa = ctk.CTkFrame(self.metrics_frame, corner_radius=10, fg_color="#1E293B")
        self.card_wa.grid(row=0, column=1, padx=(5, 5), sticky="ew")
        self.lbl_card_wa_title = ctk.CTkLabel(self.card_wa, text="WHATSAPP / HP", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94A3B8")
        self.lbl_card_wa_title.pack(anchor="w", padx=15, pady=(10, 0))
        self.lbl_card_wa_val = ctk.CTkLabel(self.card_wa, text="0", font=ctk.CTkFont(size=26, weight="bold"), text_color="#22C55E")
        self.lbl_card_wa_val.pack(anchor="w", padx=15, pady=(0, 10))

        # Metric 3: Email
        self.card_email = ctk.CTkFrame(self.metrics_frame, corner_radius=10, fg_color="#1E293B")
        self.card_email.grid(row=0, column=2, padx=(10, 0), sticky="ew")
        self.lbl_card_email_title = ctk.CTkLabel(self.card_email, text="EMAIL RESMI", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94A3B8")
        self.lbl_card_email_title.pack(anchor="w", padx=15, pady=(10, 0))
        self.lbl_card_email_val = ctk.CTkLabel(self.card_email, text="0", font=ctk.CTkFont(size=26, weight="bold"), text_color="#A855F7")
        self.lbl_card_email_val.pack(anchor="w", padx=15, pady=(0, 10))

        # --- Progress Bar & Status Text ---
        self.status_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.status_frame.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        self.lbl_status = ctk.CTkLabel(self.status_frame, text="Status: Siap melakukan pencarian.", font=ctk.CTkFont(size=12))
        self.lbl_status.pack(side="left")

        self.progress_bar = ctk.CTkProgressBar(self.status_frame, height=12)
        self.progress_bar.set(0)
        self.progress_bar.pack(side="right", fill="x", expand=True, padx=(20, 0))

        # --- Quick Action Export Toolbar (Always visible on top of table) ---
        self.toolbar_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.toolbar_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        self.btn_top_excel = ctk.CTkButton(
            self.toolbar_frame,
            text="📊 Ekspor ke Excel (.xlsx)",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            height=32,
            command=self.export_excel
        )
        self.btn_top_excel.pack(side="left", padx=(0, 8))

        self.btn_top_csv = ctk.CTkButton(
            self.toolbar_frame,
            text="📄 Ekspor ke CSV (.csv)",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            height=32,
            command=self.export_csv
        )
        self.btn_top_csv.pack(side="left", padx=(0, 8))

        self.btn_top_folder = ctk.CTkButton(
            self.toolbar_frame,
            text="📂 Buka Folder Hasil (Auto-Save)",
            font=ctk.CTkFont(size=12),
            fg_color="#475569",
            hover_color="#334155",
            height=32,
            command=self.open_output_folder
        )
        self.btn_top_folder.pack(side="left")

        # --- Live Data Table (Treeview) ---
        self.table_frame = ctk.CTkFrame(self.main_frame, corner_radius=10)
        self.table_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        self.table_frame.grid_columnconfigure(0, weight=1)
        self.table_frame.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        background="#1E293B",
                        foreground="#F1F5F9",
                        fieldbackground="#1E293B",
                        rowheight=26,
                        font=("Calibri", 10))
        style.configure("Treeview.Heading",
                        background="#0F172A",
                        foreground="#38BDF8",
                        font=("Calibri", 10, "bold"))
        style.map("Treeview", background=[("selected", "#0284C7")])

        cols = ("no", "nama", "wa", "email", "telepon", "provinsi", "kabupaten", "npwp", "pimpinan")
        self.tree = ttk.Treeview(self.table_frame, columns=cols, show="headings", selectmode="extended")

        self.tree.heading("no", text="No")
        self.tree.heading("nama", text="Nama Badan Usaha")
        self.tree.heading("wa", text="WhatsApp / HP")
        self.tree.heading("email", text="Email Perusahaan")
        self.tree.heading("telepon", text="Telepon Kantor")
        self.tree.heading("provinsi", text="Provinsi")
        self.tree.heading("kabupaten", text="Kabupaten/Kota")
        self.tree.heading("npwp", text="NPWP")
        self.tree.heading("pimpinan", text="Pimpinan/PJBU")

        self.tree.column("no", width=45, anchor="center")
        self.tree.column("nama", width=220, anchor="w")
        self.tree.column("wa", width=120, anchor="center")
        self.tree.column("email", width=180, anchor="w")
        self.tree.column("telepon", width=100, anchor="w")
        self.tree.column("provinsi", width=110, anchor="center")
        self.tree.column("kabupaten", width=120, anchor="w")
        self.tree.column("npwp", width=110, anchor="center")
        self.tree.column("pimpinan", width=130, anchor="w")

        tree_scroll_y = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        tree_scroll_x = ttk.Scrollbar(self.table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x.grid(row=1, column=0, sticky="ew")

        # --- Activity Log Console ---
        self.lbl_log = ctk.CTkLabel(self.main_frame, text="Log Aktivitas Scraping:", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_log.grid(row=4, column=0, sticky="w", pady=(0, 2))

        self.log_textbox = ctk.CTkTextbox(self.main_frame, height=125, font=ctk.CTkFont(family="Consolas", size=11))
        self.log_textbox.grid(row=5, column=0, sticky="ew")

        self.log("Aplikasi LPJK Contact Scraper siap digunakan.")
        self.log("Mode: 'Ambil SEMUA Data' aktif secara default (tanpa batas).")

    def toggle_all_pages(self):
        """Toggle page limit entry enabled/disabled based on checkbox."""
        if self.chk_all_pages.get():
            self.entry_pages.configure(state="disabled")
        else:
            self.entry_pages.configure(state="normal")

    def log(self, message):
        """Append message to log console."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}\n"
        self.log_textbox.insert("end", formatted)
        self.log_textbox.see("end")

    def on_provinsi_change(self, choice):
        """Asynchronously load regencies for selected province."""
        if choice == "Semua Provinsi" or choice == "Nasional":
            self.cb_kabupaten.configure(values=["Semua Kabupaten"])
            self.cb_kabupaten.set("Semua Kabupaten")
            return

        def load():
            self.log(f"Memuat daftar kabupaten untuk provinsi {choice}...")
            kabs = fetch_kabupaten(choice)
            if kabs:
                self.cb_kabupaten.configure(values=["Semua Kabupaten"] + kabs)
            else:
                self.cb_kabupaten.configure(values=["Semua Kabupaten"])
            self.cb_kabupaten.set("Semua Kabupaten")

        threading.Thread(target=load, daemon=True).start()

    def update_metrics(self, total, wa, email):
        """Update KPI metrics display."""
        self.lbl_card_total_val.configure(text=f"{total:,}")
        self.lbl_card_wa_val.configure(text=f"{wa:,}")
        self.lbl_card_email_val.configure(text=f"{email:,}")

    def update_status(self, text, progress_val, metrics):
        """Thread-safe UI status update."""
        self.after(0, lambda: self._apply_status(text, progress_val, metrics))

    def _apply_status(self, text, progress_val, metrics):
        self.lbl_status.configure(text=f"Status: {text}")
        if progress_val >= 0:
            self.progress_bar.set(progress_val)
        if metrics:
            self.update_metrics(metrics.get("total", 0), metrics.get("wa", 0), metrics.get("email", 0))

    def add_row_to_table(self, item):
        """Insert scraped item into Treeview table."""
        self.after(0, lambda: self.tree.insert("", "end", values=(
            item.get("no", ""),
            item.get("nama", ""),
            item.get("whatsapp", "") or "-",
            item.get("email", "") or "-",
            item.get("telepon", "") or "-",
            item.get("provinsi", ""),
            item.get("kabupaten", ""),
            item.get("npwp", ""),
            item.get("pimpinan", "") or "-"
        )))

    def submit_search_now(self):
        """Allow user to force submit the search form."""
        if self.scraper and self.is_scraping:
            self.scraper.submit_search_now()

    def start_scraping_thread(self):
        """Validate input and launch scraping in background thread."""
        if self.is_scraping:
            return

        keyword = self.entry_keyword.get().strip()
        jenis = self.jenis_var.get()
        prov = self.cb_provinsi.get()
        prov_val = "" if prov == "Semua Provinsi" else prov
        kab = self.cb_kabupaten.get()
        kab_val = "" if kab == "Semua Kabupaten" else kab
        kual_choice = self.cb_kualifikasi.get()
        kual_val = self.kual_map.get(kual_choice, "")

        if self.chk_all_pages.get():
            pages = 0  # 0 means unlimited pages
        else:
            try:
                pages = int(self.entry_pages.get().strip())
                if pages < 1:
                    pages = 1
            except ValueError:
                pages = 50
                self.entry_pages.delete(0, "end")
                self.entry_pages.insert(0, "50")

        fetch_details = bool(self.switch_details.get())
        show_browser = bool(self.switch_browser.get())

        # Clear previous table results
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.scraped_data = []
        self.update_metrics(0, 0, 0)
        self.progress_bar.set(0)

        self.is_scraping = True
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_submit_now.configure(state="normal")

        def worker():
            self.scraper = LPJKScraper(
                log_callback=lambda msg: self.after(0, lambda: self.log(msg)),
                status_callback=self.update_status,
                row_callback=self.add_row_to_table
            )
            results = self.scraper.scrape(
                keyword=keyword,
                jenis=jenis,
                provinsi=prov_val,
                kabupaten=kab_val,
                kualifikasi=kual_val,
                max_pages=pages,
                fetch_details=fetch_details,
                headless=not show_browser
            )
            self.scraped_data = results
            self.is_scraping = False
            self.after(0, self._on_scraping_finished)

        threading.Thread(target=worker, daemon=True).start()

    def _on_scraping_finished(self):
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.btn_submit_now.configure(state="disabled")
        total = len(self.scraped_data)
        if total > 0:
            wa_count = sum(1 for d in self.scraped_data if d.get("whatsapp"))
            em_count = sum(1 for d in self.scraped_data if d.get("email"))
            messagebox.showinfo(
                "Scraping Selesai",
                f"Berhasil mengekstrak {total:,} data perusahaan!\n\n"
                f"• WhatsApp Ditemukan: {wa_count:,}\n"
                f"• Email Ditemukan: {em_count:,}\n\n"
                f"Data juga otomatis tersimpan di folder 'hasil_scraping'.\n"
                f"Silakan klik tombol Ekspor untuk menyimpan file kustom."
            )
        else:
            messagebox.showinfo(
                "Selesai",
                "Scraping selesai. Jika data kosong, pastikan reCAPTCHA di browser tercentang dan hasil pencarian telah muncul sebelum waktu tunggu habis."
            )

    def stop_scraping(self):
        """User stops scraping."""
        if self.scraper:
            self.scraper.stop()
        self.btn_stop.configure(state="disabled")
        self.btn_submit_now.configure(state="disabled")
        self.log("Meminta scraper berhenti. Seluruh data yang sudah terkumpul tersimpan dengan aman!")

    def export_excel(self):
        """Export current data to Excel (.xlsx)."""
        if not self.scraped_data:
            messagebox.showwarning("Peringatan", "Belum ada data hasil scraping untuk diekspor.")
            return

        out_dir = os.path.join(os.getcwd(), "hasil_scraping")
        os.makedirs(out_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"LPJK_Kontak_WA_Email_{len(self.scraped_data)}_Data_{timestamp}.xlsx"

        file_path = filedialog.asksaveasfilename(
            initialdir=out_dir,
            initialfile=default_name,
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx")]
        )
        if file_path:
            try:
                export_to_excel(self.scraped_data, file_path)
                self.log(f"Data berhasil diekspor ke Excel: {file_path}")
                res = messagebox.askyesno("Ekspor Sukses", f"File Excel ({len(self.scraped_data):,} baris) berhasil disimpan ke:\n{file_path}\n\nBuka file sekarang?")
                if res:
                    os.startfile(file_path)
            except Exception as e:
                messagebox.showerror("Error Ekspor", f"Gagal mengekspor data: {e}")

    def export_csv(self):
        """Export current data to CSV (.csv)."""
        if not self.scraped_data:
            messagebox.showwarning("Peringatan", "Belum ada data hasil scraping untuk diekspor.")
            return

        out_dir = os.path.join(os.getcwd(), "hasil_scraping")
        os.makedirs(out_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"LPJK_Kontak_WA_Email_{len(self.scraped_data)}_Data_{timestamp}.csv"

        file_path = filedialog.asksaveasfilename(
            initialdir=out_dir,
            initialfile=default_name,
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")]
        )
        if file_path:
            try:
                export_to_csv(self.scraped_data, file_path)
                self.log(f"Data berhasil diekspor ke CSV: {file_path}")
                messagebox.showinfo("Ekspor Sukses", f"File CSV berhasil disimpan ke:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Error Ekspor", f"Gagal mengekspor data: {e}")

    def open_output_folder(self):
        """Open the results folder in Windows Explorer."""
        out_dir = os.path.join(os.getcwd(), "hasil_scraping")
        os.makedirs(out_dir, exist_ok=True)
        os.startfile(out_dir)

    def on_closing(self):
        """Cleanup before exit."""
        if self.scraper:
            self.scraper.close()
        self.destroy()

if __name__ == "__main__":
    app = LPJKScraperApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
