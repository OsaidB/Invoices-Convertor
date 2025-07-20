#main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import requests
import os
import tempfile
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

@app.post("/reprocess-mismatched")
def reprocess_mismatched():
    try:
        print("🔁 Fixing mismatched invoices...")
        fix_mismatched_invoices()

        print("📂 Moving matched invoices back...")
        move_matched_back()

        print("📤 Sending reprocessed invoices to backend...")
        send_invoices_to_api(json_base_dir="jsons")

        return JSONResponse(content={"status": "✅ Reprocessing complete"}, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reprocessing failed: {str(e)}")
