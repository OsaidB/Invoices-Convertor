# main.py

from fastapi import FastAPI, HTTPException
import requests
import os
import tempfile
from datetime import datetime

from invoice_processor.convert_invoice import process_invoice_pdf
from invoice_processor.fix_mismatched_invoices import fix_mismatched_invoice
from invoice_processor.schemas import (
    InvoiceRequest,
    PendingInvoice,
    PendingInvoiceItem,
)

import json

app = FastAPI()


@app.post("/process-invoice", response_model=PendingInvoice)
def process_invoice(req: InvoiceRequest):
    try:
        response = requests.get(req.url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download PDF: {str(e)}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(response.content)
        tmp_path = tmp_file.name

    try:
        invoice_data = process_invoice_pdf(tmp_path)
        invoice_data["pdfUrl"] = req.url
        invoice_data["confirmed"] = False
        invoice_data["parsedAt"] = datetime.utcnow().isoformat()

        return invoice_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

    finally:
        os.remove(tmp_path)


@app.post("/fix-mismatched", response_model=PendingInvoice)
def fix_mismatched_from_url(req: InvoiceRequest):
    try:
        response = requests.get(req.url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download PDF: {str(e)}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(response.content)
        tmp_path = tmp_file.name

    try:
        invoice_data = process_invoice_pdf(tmp_path)

        # print("📦 before ba3basing Sending invoice to backend:")
        # print(json.dumps(invoice_data, indent=2, ensure_ascii=False))  # 👈 Print here

        # print("📦📦📦📦📦 req.originalId:")
        # print(req.originalId)
        # ✅ Set reprocessedFromId BEFORE modifying the object
        if req.originalId and not invoice_data.get("reprocessedFromId"):
            invoice_data["reprocessedFromId"] = req.originalId
            invoice_data.pop("id", None)

        invoice_data = fix_mismatched_invoice(invoice_data)

        invoice_data["pdfUrl"] = req.url
        invoice_data["confirmed"] = False
        invoice_data["parsedAt"] = datetime.utcnow().isoformat()

        if invoice_data.get("totalMatch") is True and not req.originalId:
            print(
                "⚠️ Invoice is already matched and not a reprocessed request. Skipping send."
            )
            return PendingInvoice(**invoice_data)

        print("🧾 Final invoice data to send:")
        print(json.dumps(invoice_data, indent=2, ensure_ascii=False))

        return PendingInvoice(**invoice_data)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fix mismatched invoice: {str(e)}"
        )

    finally:
        os.remove(tmp_path)
