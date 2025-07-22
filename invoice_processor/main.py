# main.py

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import requests
import os
import tempfile
from datetime import datetime

from invoice_processor.parse_invoice.convert_invoice import process_invoice_pdf
from invoice_processor.fix_mismatched.fix_mismatched_invoices import fix_mismatched_invoice
from invoice_processor.send_invoices import send_invoice_to_api
from invoice_processor.models.schemas import InvoiceRequest, PendingInvoice, PendingInvoiceItem

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

        send_invoice_to_api(invoice_data)
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
        invoice_data = fix_mismatched_invoice(invoice_data)
        invoice_data["pdfUrl"] = req.url
        invoice_data["confirmed"] = False
        invoice_data["parsedAt"] = datetime.utcnow().isoformat()

        send_invoice_to_api(invoice_data)
        return invoice_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fix mismatched invoice: {str(e)}")

    finally:
        os.remove(tmp_path)
