#fix_mismatched_invoices.py

import json
import os
from decimal import Decimal, ROUND_HALF_UP

def fix_mismatched_invoices(json_base_dir="jsons/mismatched"):
    """
    Process JSON invoice files in the mismatched directory to fix total mismatches
    by adjusting the quantity field where total_match is false.
    Overrides the JSON file only if the mismatch is resolved.
    """
    # Ensure the base directory exists
    if not os.path.exists(json_base_dir):
        print(f"Directory {json_base_dir} not found.")
        return

    # Iterate over all JSON files in the mismatched directory and its subdirectories
    for root, dirs, files in os.walk(json_base_dir):
        for filename in files:
            if filename.endswith(".json"):
                json_path = os.path.join(root, filename)
                print(f"Processing {json_path}")

                # Read the existing JSON file
                with open(json_path, "r", encoding="utf-8") as f:
                    invoice_data = json.load(f)

                # Check if total_match is false
                if not invoice_data.get("total_match", True):
                    print(f"Found mismatch in {filename}, attempting to fix...")

                    # Recalculate quantities for items
                    calculated_total = Decimal("0.00")
                    modified = False

                    for item in invoice_data["items"]:
                        qty = Decimal(str(item["quantity"]))
                        unit_price = Decimal(str(item["unit_price"]))
                        total_price = Decimal(str(item["total_price"]))

                        # Recalculate quantity as total_price / unit_price
                        if unit_price != 0:  # Avoid division by zero
                            new_quantity = (total_price / unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                            if new_quantity != qty:
                                item["quantity"] = float(new_quantity)
                                modified = True
                                print(f"Adjusted quantity for {item['description']} from {qty} to {new_quantity}")

                        # Update calculated total with the expected value
                        expected_total_price = (Decimal(str(item["quantity"])) * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        calculated_total += expected_total_price

                    # Revalidate total_match
                    written_total = Decimal(str(invoice_data["total"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    new_total_match = (calculated_total == written_total)

                    print(f"Recalculated total: {calculated_total}, Written total: {written_total}, New match: {new_total_match}")

                    # Override the JSON only if the mismatch is resolved
                    if modified and new_total_match:
                        invoice_data["total_match"] = True
                        with open(json_path, "w", encoding="utf-8") as f:
                            json.dump(invoice_data, f, ensure_ascii=False, indent=2)
                        print(f"✅ Overwrote {json_path} with fixed data: {invoice_data}")
                    else:
                        print(f"No change made to {json_path} (mismatch not resolved or no adjustment needed)")
                else:
                    print(f"Skipping {filename}, total_match is already True")

if __name__ == "__main__":
    fix_mismatched_invoices()