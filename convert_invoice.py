import fitz
import json
import re
import unicodedata
import os

# Helper: Normalize Arabic text
def normalize_arabic(text):
    return unicodedata.normalize('NFKC', text).replace("ـ", "").strip()

# Load PDF and extract lines
input_file = "report (3).pdf"  # Store the input file name
doc = fitz.open(input_file)
lines = [line.strip() for line in doc[0].get_text().splitlines() if line.strip()]
print("All lines extracted:", lines)

invoice_data = {
    "date": None,
    # "customer": "جمال البابا",
    "items": [],
    "total": None,
    "net": None,
    "worksite": None  # New field for worksite
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
    worksite_line = worksite_lines[-1]  # Take the last occurrence
    # Normalize the line before removing "ملاحظات"
    normalized_line = normalize_arabic(worksite_line)
    # Remove "ملاحظات" using the normalized form
    worksite = normalized_line.replace(normalize_arabic("ملاحظات"), "").strip()
    invoice_data["worksite"] = worksite
    print(f"Worksite extracted: {invoice_data['worksite']}")
else:
    print("Could not find 'ملاحظات' for worksite extraction")

# Find the start of items (after headers)
start_index = 0
for i, line in enumerate(lines):
    norm_line = normalize_arabic(line)
    if "السعر" in norm_line:  # Last header line
        start_index = i + 1
        break
print(f"Starting item parsing at index {start_index}")

# Process items
i = start_index
while i < len(lines):
    desc_lines = []

    # Collect description-like lines until we hit a price (numeric with decimals)
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

    # Ensure we have at least 2 lines left (unit price, total price)
    if i + 1 >= len(lines):
        print(f"Breaking loop at index {i} due to insufficient lines")
        break

    try:
        print(f"Attempting to parse prices at index {i}")
        # Extract unit price and total price in the correct order
        unit_price = float(lines[i].replace(",", ""))  # First numeric is unit price
        total_price = float(lines[i + 1].replace(",", ""))  # Second numeric is total price
        i += 2  # Move past unit and total price

        # Check for standalone quantity within desc_lines
        quantity = 1.0
        desc_lines_cleaned = []
        for line in desc_lines:
            if re.match(r"^\d+$", line) and not any(skip in normalize_arabic(line) for skip in SKIP_WORDS):
                quantity = float(line)
                print(f"Found standalone quantity in desc_lines: {quantity}")
                continue  # Skip adding this line to description
            desc_lines_cleaned.append(line)

        # Join description lines and clean up
        description = " ".join(desc_lines_cleaned).strip()
        description = re.sub(r"^\d+\s*", "", description).strip()  # Remove leading numbers
        description = description.replace("كيلو5", "كيلو25")  # Correct typo for previous report
        norm_desc = normalize_arabic(description)
        print(f"Constructed description: '{description}'")

        # Extract quantity from description if not already set
        if quantity == 1.0 and description:
            # Look for quantities like "ارضي40", "عمود40", or "زوايا10"
            quantity_match = re.search(r"(ارضي|عمود|زوايا)(\d+)", description)
            if quantity_match:
                quantity = float(quantity_match.group(2))
                print(f"Extracted quantity from description (ارضي|عمود|زوايا): {quantity}")
                description = description.replace(quantity_match.group(0), quantity_match.group(1)).strip()
            else:
                # Look for trailing numbers (e.g., "شبحات فورسيلنك10")
                quantity_match = re.search(r"(\d+)$", description)
                if quantity_match and not re.search(r"كيلو\d+", description):
                    quantity = float(quantity_match.group(1))
                    print(f"Extracted trailing quantity from description: {quantity}")
                    description = description.replace(quantity_match.group(1), "").strip()

        # Clean up trailing "1" from descriptions where it's not part of the item name
        description = re.sub(r"\s*1$", "", description).strip()

        if (
            len(norm_desc) > 2 and
            not any(skip in norm_desc for skip in SKIP_WORDS)
        ):
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

# Generate output file name by replacing "report" with "invoice"
base_name = os.path.splitext(input_file)[0]  # Get the base name (e.g., "report (5)")
output_base_name = base_name.replace("report", "invoice")  # Replace "report" with "invoice"
output_file = output_base_name + ".json"  # Add .json extension (e.g., "invoice (5).json")

# Export JSON with the dynamic output file name
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(invoice_data, f, ensure_ascii=False, indent=2)
print(f"✅ Fully cleaned JSON saved as {output_file}")
print("Final invoice data:", invoice_data)