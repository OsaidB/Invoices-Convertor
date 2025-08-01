from decimal import Decimal, ROUND_HALF_UP


def fix_mismatched_invoice(invoice_data: dict) -> dict:
    """
    Fix mismatched totals in a single invoice dictionary by recalculating quantities.
    Returns the modified invoice dictionary with reprocessedFromId set.
    """

    if invoice_data.get("totalMatch", True):
        print("✅ Invoice already matched. No changes made.")
        return invoice_data

    print("🔧 Fixing mismatched invoice...")

    calculated_total = Decimal("0.00")

    # 🔁 Step 1: Convert snake_case to camelCase for internal use
    for item in invoice_data.get("items", []):
        if "unit_price" in item:
            item["unitPrice"] = item.pop("unit_price")
        if "total_price" in item:
            item["totalPrice"] = item.pop("total_price")

    # 🧮 Step 2: Fix mismatched quantities
    for item in invoice_data.get("items", []):
        qty = Decimal(str(item["quantity"]))
        unit_price = Decimal(str(item["unitPrice"]))
        total_price = Decimal(str(item["totalPrice"]))

        if unit_price != 0:
            new_quantity = (total_price / unit_price).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if new_quantity != qty:
                item["quantity"] = float(new_quantity)
                print(
                    f"✏️ Adjusted quantity for '{item['description']}' from {qty} → {new_quantity}"
                )

        expected_total = (Decimal(str(item["quantity"])) * unit_price).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        calculated_total += expected_total

    written_total = Decimal(str(invoice_data.get("total", 0))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    invoice_data["totalMatch"] = calculated_total == written_total

    if invoice_data["totalMatch"]:
        print(f"✅ Mismatch resolved. New total: {calculated_total}")
    else:
        print(
            f"❌ Mismatch remains. Calculated: {calculated_total}, Written: {written_total}"
        )

    # 🔁 Step 3: Always convert back to snake_case before returning
    for item in invoice_data.get("items", []):
        if "unitPrice" in item:
            item["unit_price"] = item.pop("unitPrice")
        if "totalPrice" in item:
            item["total_price"] = item.pop("totalPrice")

    return invoice_data
