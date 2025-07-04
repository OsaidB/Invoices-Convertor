from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import os
import tempfile
from convert_invoice import process_invoice_pdf

app = FastAPI()

class InvoiceRequest(BaseModel):
    url: str

@app.post("/process-invoice")
def process_invoice(req: InvoiceRequest):
    url = req.url

    # Step 1: Download PDF to a temporary file
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download PDF: {e}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(response.content)
        tmp_path = tmp_file.name

    # Step 2: Process PDF
    try:
        invoice_data = process_invoice_pdf(tmp_path, "pdfs", "jsons")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {e}")
    finally:
        os.remove(tmp_path)

    return invoice_data
