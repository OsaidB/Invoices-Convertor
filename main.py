# main.py

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime
import requests
import os
import tempfile
import uuid

from convert_invoice import process_invoice_pdf

from fix_mismatched_invoices import fix_mismatched_invoices
from move_matched_back import move_matched_back
from send_invoices import send_invoices_to_api
from fastapi.responses import JSONResponse

app = FastAPI()

class InvoiceRequest(BaseModel):
    url: str


class PendingInvoiceItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    total_price: float

class PendingInvoice(BaseModel):
    date: str
    netTotal: float
    total: float
    worksiteName: str
    items: list[PendingInvoiceItem]
    totalMatch: bool
    pdfUrl: str
    confirmed: bool
    parsedAt: str

@app.post("/process-invoice", response_model=PendingInvoice)
def process_invoice(req: InvoiceRequest):
    url = req.url

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download PDF: {str(e)}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(response.content)
        tmp_path = tmp_file.name

    try:
        invoice_data = process_invoice_pdf(tmp_path, "pdfs", "jsons")

        return PendingInvoice(
            date=invoice_data.get("date", datetime.now().isoformat()),
            netTotal=invoice_data.get("netTotal", invoice_data.get("total", 0.0)),
            total=invoice_data.get("total", 0.0),
            worksiteName=invoice_data.get("worksiteName", "other"),
            items=invoice_data.get("items", []),
            totalMatch=invoice_data.get("total_match", False),
            pdfUrl=url,  # ✅ Use original source URL, not local
            confirmed=False,
            parsedAt=invoice_data.get("parsedAt", datetime.utcnow().isoformat())
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

    finally:
        os.remove(tmp_path)

# ✅ Updated: fix-mismatched endpoint using full pipeline
@app.post("/fix-mismatched")
def fix_mismatched_from_url(req: InvoiceRequest):
    url = req.url

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download PDF: {str(e)}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(response.content)
        tmp_path = tmp_file.name

    try:
        # 1. Process invoice normally
        invoice_data = process_invoice_pdf(tmp_path, "pdfs", "jsons")

        # 2. Save to mismatched folder as .json
        mismatched_dir = os.path.join("jsons", "mismatched", datetime.now().date().isoformat())
        os.makedirs(mismatched_dir, exist_ok=True)

        filename = f"invoice_{uuid.uuid4().hex[:8]}.json"
        json_path = os.path.join(mismatched_dir, filename)

        with open(json_path, "w", encoding="utf-8") as f:
            import json
            json.dump(invoice_data, f, ensure_ascii=False, indent=2)

        print(f"📥 Saved invoice JSON to {json_path}")

        # 3. Apply fixing logic
        print("🔁 Fixing mismatches...")
        fix_mismatched_invoices()

        print("📂 Moving matched invoices...")
        move_matched_back()

        print("📤 Sending fixed invoices to backend...")
        send_invoices_to_api(json_base_dir="jsons")

        return JSONResponse(content={"status": "✅ Mismatch fixed and invoice reprocessed"}, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fix mismatched invoice: {str(e)}")

    finally:
        os.remove(tmp_path)
