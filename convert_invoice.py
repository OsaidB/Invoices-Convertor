# File: convert_invoice.py
import fitz
import json
import re
import unicodedata
import os

# Helper: Normalize Arabic text
def normalize_arabic(text):
    return unicodedata.normalize('NFKC', text).replace("ـ", "").strip()

def process_invoice_pdf(input_file, pdf_output_dir="pdfs", json_output_dir="jsons"):
    """
    Process a PDF invoice file and return the extracted data as a dictionary.
    Saves the PDF and JSON to specified directories based on the date (MM-DD-YYYY_HHMMSS) in year-based subdirectories.
    Returns the invoice data dictionary.
    """
    doc = fitz.open(input_file)
    lines = [line.strip() for line in doc[0].get_text().splitlines() if line.strip()]
    print("All lines extracted:", lines)

    invoice_data = {
        "date": None,
        # "customer": "جمال البابا",
        "items": [],
        "total": None,
        "net": None,
        "worksite": None
    }

    # Extract date
    for line in lines:
        if re.match(r"\d{1,2}/\d{1,2}/\d{4}", line):
            invoice_data["date"] = line
            break
    print("Date extracted:", invoice_data["date"])

    # Define keywords to skip (normalized)
    SKIP_WORDS = [
        "المبلغ", "الصافي", "المجموع", "ILS",
        "شكرا", "Debit", "قرب", "النقدي", "رقم", "null", "Systems", "المستخدم",
        "مبيعات", "التاريخ", "الزبون", "الخص#البيان", "الكمي", "السعر", "جمال البابا"
    ]
    SKIP_WORDS = [normalize_arabic(w) for w in SKIP_WORDS]

    # Extract worksite name (take the last occurrence of "ملاحظات")
    worksite_lines = [line for line in lines if "ملاحظات" in normalize_arabic(line)]
    if worksite_lines:
        worksite_line = worksite_lines[-1]
        normalized_line = normalize_arabic(worksite_line)
        worksite = normalized_line.replace(normalize_arabic("ملاحظات"), "").strip()
        invoice_data["worksite"] = worksite
        print(f"Worksite extracted: {invoice_data['worksite']}")
    else:
        invoice_data["worksite"] = "other"
        print("No 'ملاحظات' found, worksite set to 'other'")

    print(f"Confirmed worksite before item processing: {invoice_data['worksite']}")

    # Find the start of items
    start_index = 0
    for i, line in enumerate(lines):
        norm_line = normalize_arabic(line)
        if "السعر" in norm_line:
            start_index = i + 1
            break
    print(f"Starting item parsing at index {start_index}")

    # Process items
    i = start_index
    while i < len(lines):
        desc_lines = []
        print(f"\nProcessing index {i}, current line: '{lines[i]}'")
        while i < len(lines) and not re.match(r"^\d+\.\d{2}$", lines[i]):
            norm_line = normalize_arabic(lines[i])
            if any(skip in norm_line for skip in SKIP_WORDS) or re.match(r"^\d{1,3},\d{3}\.\d{2}$", norm_line):
                print(f"Skipping line '{lines[i]}' due to skip condition")
                i += 1
                continue
            desc_lines.append(lines[i])
            print(f"Added to description: '{lines[i]}'")
            i += 1

        if i + 1 >= len(lines):
            print(f"Breaking loop at index {i} due to insufficient lines")
            break

        try:
            print(f"Attempting to parse prices at index {i}")
            unit_price = float(lines[i].replace(",", ""))
            total_price = float(lines[i + 1].replace(",", ""))
            i += 2

            quantity = 1.0
            desc_lines_cleaned = []
            for line in desc_lines:
                if re.match(r"^\d+$", line) and not any(skip in normalize_arabic(line) for skip in SKIP_WORDS):
                    quantity = float(line)
                    print(f"Found standalone quantity in desc_lines: {quantity}")
                    continue
                desc_lines_cleaned.append(line)

            description = " ".join(desc_lines_cleaned).strip()
            description = re.sub(r"^\d+\s*", "", description).strip()
            description = description.replace("كيلو5", "كيلو25")
            norm_desc = normalize_arabic(description)
            print(f"Constructed description: '{description}'")

            if quantity == 1.0 and description:
                quantity_match = re.search(r"(ارضي|عمود|زوايا)(\d+)", description)
                if quantity_match:
                    quantity = float(quantity_match.group(2))
                    print(f"Extracted quantity from description (ارضي|عمود|زوايا): {quantity}")
                    description = description.replace(quantity_match.group(0), quantity_match.group(1)).strip()
                else:
                    quantity_match = re.search(r"(\d+)$", description)
                    if quantity_match and not re.search(r"كيلو\d+", description):
                        quantity = float(quantity_match.group(1))
                        print(f"Extracted trailing quantity from description: {quantity}")
                        description = description.replace(quantity_match.group(1), "").strip()

            description = re.sub(r"\s*1$", "", description).strip()

            if len(norm_desc) > 2 and not any(skip in norm_desc for skip in SKIP_WORDS):
                item = {
                    "description": description,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_price": total_price
                }
                invoice_data["items"].append(item)
                print(f"Added item: {item}")

        except (ValueError, IndexError) as e:
            print(f"Error at index {i}: {e}, skipping to next line")
            i += 1

    # Extract totals
    for line in lines:
        norm_line = normalize_arabic(line)
        if "المجموع" in norm_line:
            match = re.search(r"([\d,]+\.\d{2})", line)
            if match:
                invoice_data["total"] = float(match.group(1).replace(",", ""))
                print(f"Total extracted: {invoice_data['total']}")
        if "الصافي" in norm_line:
            match = re.search(r"([\d,]+\.\d{2})", line)
            if match:
                invoice_data["net"] = float(match.group(1).replace(",", ""))
                print(f"Net extracted: {invoice_data['net']}")
        if not invoice_data["net"] and invoice_data["total"]:
            invoice_data["net"] = invoice_data["total"]
            print(f"Net set to total: {invoice_data['net']}")

    # Calculate total from items and compare with written total
    calculated_total = sum(item["total_price"] for item in invoice_data["items"])
    invoice_data["total_match"] = calculated_total == invoice_data["total"]
    print(f"Calculated total: {calculated_total}, Written total: {invoice_data['total']}, Match: {invoice_data['total_match']}")

    print(f"Final worksite value before export: {invoice_data['worksite']}")

    # Create output directories if they don't exist
    os.makedirs(pdf_output_dir, exist_ok=True)
    os.makedirs(json_output_dir, exist_ok=True)

    # Generate output file name using date if available
    if invoice_data["date"]:
        # Parse date (e.g., "25/2/2025 09:17:15" -> MM-DD-YYYY_HHMMSS)
        date_match = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{2}):(\d{2}):(\d{2})", invoice_data["date"])
        if date_match:
            day, month, year, hour, minute, second = date_match.groups()
            # Format as MM-DD-YYYY_HHMMSS
            date_str = f"{int(month):02d}-{int(day):02d}-{year}_{hour}{minute}{second}"
            # Create year-based subdirectories
            pdf_year_dir = os.path.join(pdf_output_dir, year)
            json_year_dir = os.path.join(json_output_dir, year)
            os.makedirs(pdf_year_dir, exist_ok=True)
            os.makedirs(json_year_dir, exist_ok=True)
            pdf_output_file = os.path.join(pdf_year_dir, f"{date_str}.pdf")
            json_output_file = os.path.join(json_year_dir, f"{date_str}.json")
        else:
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            output_base_name = base_name.replace("report", "invoice")
            pdf_output_file = os.path.join(pdf_output_dir, f"{output_base_name}.pdf")
            json_output_file = os.path.join(json_output_dir, f"{output_base_name}.json")
    else:
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_base_name = base_name.replace("report", "invoice")
        pdf_output_file = os.path.join(pdf_output_dir, f"{output_base_name}.pdf")
        json_output_file = os.path.join(json_output_dir, f"{output_base_name}.json")

    # Ensure unique filenames by appending index if file exists
    pdf_base, pdf_ext = os.path.splitext(pdf_output_file)
    json_base, json_ext = os.path.splitext(json_output_file)
    pdf_index = 0
    json_index = 0
    while os.path.exists(pdf_output_file):
        pdf_output_file = f"{pdf_base}_{pdf_index}{pdf_ext}"
        pdf_index += 1
    while os.path.exists(json_output_file):
        json_output_file = f"{json_base}_{json_index}{json_ext}"
        json_index += 1

    if not invoice_data["worksite"] or invoice_data["worksite"] == "":
        invoice_data["worksite"] = "other"
        print("Force-set worksite to 'other' due to empty value")

    # Export JSON
    with open(json_output_file, "w", encoding="utf-8") as f:
        json.dump(invoice_data, f, ensure_ascii=False, indent=2)
    print(f"✅ Fully cleaned JSON saved as {json_output_file}")
    print("Final invoice data:", invoice_data)

    return invoice_data

# For standalone execution
if __name__ == "__main__":
    input_file = "report (3).pdf"
    process_invoice_pdf(input_file)