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
    # modified = False

    print(invoice_data)

    for item in invoice_data.get("items", []):
        qty = Decimal(str(item["quantity"]))
        unit_price = Decimal(str(item["unitPrice"]))  # ✅ FIXED
        total_price = Decimal(str(item["totalPrice"]))  # ✅ FIXED

        if unit_price != 0:
            new_quantity = (total_price / unit_price).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if new_quantity != qty:
                item["quantity"] = float(new_quantity)
                # modified = True
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

    return invoice_data
