import os
import re
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def clean_whatsapp(number_str):
    """Clean phone number and return normalized international WA number."""
    if not number_str:
        return "", ""
    digits = re.sub(r"[^\d]", "", str(number_str))
    if digits.startswith("08"):
        digits = "628" + digits[2:]
    elif digits.startswith("8") and len(digits) >= 9:
        digits = "62" + digits
    elif digits.startswith("0") and len(digits) >= 9:
        digits = "62" + digits[1:]
    
    if digits.startswith("628") and len(digits) >= 10:
        return digits, f"https://wa.me/{digits}"
    return digits, ""

def export_to_excel(data_list, output_path):
    """
    Export scraped LPJK data into formatted Excel (.xlsx) file
    with active WhatsApp clickable links and styling.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Kontak LPJK"

    # Define headers
    headers = [
        "No",
        "Nama Badan Usaha",
        "WhatsApp (62...)",
        "Link WhatsApp",
        "Email Perusahaan",
        "No Telepon Kantor",
        "Pimpinan / PJBU",
        "Provinsi",
        "Kabupaten / Kota",
        "NPWP",
        "Kualifikasi",
        "Alamat Lengkap",
        "Status / Subklasifikasi"
    ]
    ws.append(headers)

    # Styles
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    regular_font = Font(name="Calibri", size=10)
    link_font = Font(name="Calibri", size=10, color="0563C1", underline="single")
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    # Apply header style
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Populate rows
    for row_idx, item in enumerate(data_list, start=2):
        wa_num = item.get("whatsapp", "")
        wa_link = item.get("wa_link", "")
        if not wa_link and wa_num:
            _, wa_link = clean_whatsapp(wa_num)

        row_data = [
            item.get("no", row_idx - 1),
            item.get("nama", ""),
            wa_num,
            "Chat WhatsApp" if wa_link else "-",
            item.get("email", ""),
            item.get("telepon", ""),
            item.get("pimpinan", ""),
            item.get("provinsi", ""),
            item.get("kabupaten", ""),
            item.get("npwp", ""),
            item.get("kualifikasi", ""),
            item.get("alamat", ""),
            item.get("subklas", "")
        ]
        ws.append(row_data)

        # Apply cell styling and hyperlinks
        for col_idx in range(1, len(headers) + 1):
            c = ws.cell(row=row_idx, column=col_idx)
            c.font = regular_font
            c.border = thin_border
            c.alignment = Alignment(vertical="center")

            # Center-align specific columns
            if col_idx in [1, 3, 4, 8, 9, 10, 11]:
                c.alignment = Alignment(horizontal="center", vertical="center")

            # Add WhatsApp Clickable Hyperlink
            if col_idx == 4 and wa_link:
                c.hyperlink = wa_link
                c.font = link_font
                c.value = "Chat WA"

            # Add Email mailto link
            if col_idx == 5 and item.get("email"):
                c.hyperlink = f"mailto:{item.get('email')}"
                c.font = link_font

    # Adjust row height
    ws.row_dimensions[1].height = 28
    for r in range(2, len(data_list) + 2):
        ws.row_dimensions[r].height = 20

    # Auto-fit column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val = str(cell.value or "")
            if len(val) > max_len:
                max_len = len(val)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    # Save
    wb.save(output_path)
    return output_path

def export_to_csv(data_list, output_path):
    """Export to CSV UTF-8 format."""
    df = pd.DataFrame(data_list)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path

def export_to_json(data_list, output_path):
    """Export to JSON format."""
    import json
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data_list, f, ensure_ascii=False, indent=2)
    return output_path
