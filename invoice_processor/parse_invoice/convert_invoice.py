import fitz
import json
import re
import unicodedata
import os
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP


# Helper: Normalize Arabic text
def normalize_arabic(text):
    return unicodedata.normalize("NFKC", text).replace("ـ", "").strip()


def process_invoice_pdf(input_file):
    """
    Process a PDF invoice file and return the extracted data as a dictionary.
    Extracts date, worksite name, itemized data, and computes total validation.
    Does not write any files or directories.
    """
    with fitz.open(input_file) as doc:
        lines = [
            line.strip() for line in doc[0].get_text().splitlines() if line.strip()
        ]

    print("All lines extracted:", lines)

    invoice_data = {
        "date": None,
        "worksiteName": None,
        "total": None,
        "netTotal": None,
        "items": [],
    }

    # Extract date
    for line in lines:
        if re.match(r"\d{1,2}/\d{1,2}/\d{4}\s+\d{2}:\d{2}:\d{2}", line):
            date_match = re.match(
                r"(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{2}):(\d{2}):(\d{2})", line
            )
            if date_match:
                day, month, year, hour, minute, second = date_match.groups()
                invoice_data["date"] = (
                    f"{year}-{int(month):02d}-{int(day):02d}T{hour}:{minute}:{second}"
                )
                print(f"Reformatted date: {invoice_data['date']}")
            break
    print("Date extracted:", invoice_data["date"])

    # Define keywords to skip (normalized)
    SKIP_WORDS = [
        "المبلغ",
        "الصافي",
        "المجموع",
        "ILS",
        "شكرا",
        "Debit",
        "قرب",
        "النقدي",
        "رقم",
        "null",
        "Systems",
        "المستخدم",
        "مبيعات",
        "التاريخ",
        "الزبون",
        "الخص#البيان",
        "الكمي",
        "السعر",
        "جمال البابا",
    ]
    SKIP_WORDS = [normalize_arabic(w) for w in SKIP_WORDS]

    # Extract worksite name (take the last occurrence of "ملاحظات")
    worksite_lines = [line for line in lines if "ملاحظات" in normalize_arabic(line)]
    if worksite_lines:
        worksite_line = worksite_lines[-1]
        normalized_line = normalize_arabic(worksite_line)
        worksiteName = normalized_line.replace(normalize_arabic("ملاحظات"), "").strip()
        invoice_data["worksiteName"] = worksiteName
        print(f"Worksite extracted: {invoice_data['worksiteName']}")
    else:
        invoice_data["worksiteName"] = "other"
        print("No 'ملاحظات' found, worksite set to 'other'")

    print(f"Confirmed worksite before item processing: {invoice_data['worksiteName']}")

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
            if any(skip in norm_line for skip in SKIP_WORDS) or re.match(
                r"^\d{1,3},\d{3}\.\d{2}$", norm_line
            ):
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
                if re.match(r"^\d+$", line) and not any(
                    skip in normalize_arabic(line) for skip in SKIP_WORDS
                ):
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
                    print(
                        f"Extracted quantity from description (ارضي|عمود|زوايا): {quantity}"
                    )
                    description = description.replace(
                        quantity_match.group(0), quantity_match.group(1)
                    ).strip()
                else:
                    quantity_match = re.search(r"(\d+)$", description)
                    if quantity_match and not re.search(r"كيلو\d+", description):
                        quantity = float(quantity_match.group(1))
                        print(
                            f"Extracted trailing quantity from description: {quantity}"
                        )
                        description = description.replace(
                            quantity_match.group(1), ""
                        ).strip()

            description = re.sub(r"\s*1$", "", description).strip()

            if len(norm_desc) > 2 and not any(skip in norm_desc for skip in SKIP_WORDS):
                item = {
                    "description": description,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_price": total_price,
                    "materialId": None,
                }

                invoice_data["items"].append(item)
                print(f"Added item: {item}")

        except (ValueError, IndexError) as e:
            print(f"Error at index {i}: {e}, skipping to next line")
            i += 1

    # Extract totals
    for line in lines:
        norm_line = normalize_arabic(line)
        if "المجموع" in norm_line and not invoice_data["total"]:
            match = re.search(r"([\d,]+\.\d{2})", line)
            if match:
                invoice_data["total"] = float(match.group(1).replace(",", ""))
                print(f"Total extracted: {invoice_data['total']}")
        if "الصافي" in norm_line and not invoice_data["netTotal"]:
            match = re.search(r"([\d,]+\.\d{2})", line)
            if match:
                invoice_data["netTotal"] = float(match.group(1).replace(",", ""))
                print(f"Net extracted: {invoice_data['netTotal']}")

    if not invoice_data["netTotal"] and invoice_data["total"]:
        invoice_data["netTotal"] = invoice_data["total"]
        print(f"Net set to total: {invoice_data['netTotal']}")

    # Item-level validation and total verification
    item_mismatches = []
    calculated_total = Decimal("0.00")

    for item in invoice_data["items"]:
        qty = Decimal(str(item["quantity"]))
        unit_price = Decimal(str(item["unit_price"]))  # ✅ fix here
        expected_total_price = (qty * unit_price).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        actual_total_price = Decimal(str(item["total_price"])).quantize(  # ✅ fix here
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        if expected_total_price != actual_total_price:
            item_mismatches.append(
                {
                    "description": item["description"],
                    "expected": float(expected_total_price),
                    "actual": float(actual_total_price),
                }
            )

        calculated_total += expected_total_price
        qty = Decimal(str(item["quantity"]))
        unit_price = Decimal(str(item["unit_price"]))
        expected_total_price = (qty * unit_price).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        actual_total_price = Decimal(str(item["total_price"])).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        if expected_total_price != actual_total_price:
            item_mismatches.append(
                {
                    "description": item["description"],
                    "expected": float(expected_total_price),
                    "actual": float(actual_total_price),
                }
            )

        calculated_total += expected_total_price

    # Check against the written total
    if invoice_data["total"] is not None:
        written_total = Decimal(str(invoice_data["total"])).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        invoice_data["totalMatch"] = calculated_total == written_total
        print(
            f"Calculated total: {calculated_total}, Written total: {written_total}, Match: {invoice_data['totalMatch']}"
        )
    else:
        invoice_data["totalMatch"] = False
        print("❌ Written total not found in invoice")

    if item_mismatches:
        print("⚠️ Item-level mismatches found:")
        for mismatch in item_mismatches:
            print(
                f" - {mismatch['description']}: expected {mismatch['expected']}, got {mismatch['actual']}"
            )

    if not invoice_data["worksiteName"]:
        invoice_data["worksiteName"] = "other"
        print("Force-set worksite to 'other' due to empty value")

    invoice_data["confirmed"] = False
    invoice_data["parsedAt"] = datetime.utcnow().isoformat()

    print("✅ Final invoice data prepared (not saved to file)")
    # doc.close()
    return invoice_data


# For standalone testing
if __name__ == "__main__":
    input_file = "report (3).pdf"
    parsed_invoice = process_invoice_pdf(input_file)
    print(json.dumps(parsed_invoice, ensure_ascii=False, indent=2))
