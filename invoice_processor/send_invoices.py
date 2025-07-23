# invoice_rocessor/utils/send_invoices.py

import requests
from datetime import datetime

API_URL = "https://intfitout-backend-production.up.railway.app/api/invoices/pending/upload"

def send_invoice_to_api(invoice_data: dict):
    """
    Sends a single parsed or fixed invoice to the backend API, wrapped as a list and with required fields.
    """
    try:
        # Ensure required fields
        invoice_data.setdefault("id", -1)
        invoice_data.setdefault("worksiteId", -1)
        invoice_data.setdefault("confirmed", False)
        invoice_data.setdefault("parsedAt", datetime.utcnow().isoformat() + "Z")

        for item in invoice_data.get("items", []):
            item.setdefault("id", -1)
            item.setdefault("materialId", -1)

        payload = [invoice_data]  # wrap in list as required by backend

        response = requests.post(API_URL, json=payload, timeout=10)
        response.raise_for_status()
        print(f"✅ Invoice sent successfully: {response.status_code}")
        if response.text:
            print(f"Response: {response.text}")
        return response.json() if response.content else {"status": "success"}

    except requests.RequestException as e:
        print(f"❌ Failed to send invoice: {e}")
        raise
