# invoice_parser/utils/send_invoices.py

import requests

API_URL = "https://intfitout-backend-production.up.railway.app/api/invoices/pending/upload"

def send_invoice_to_api(invoice_data: dict):
    """
    Sends a single parsed or fixed invoice to the backend API.
    """
    try:
        response = requests.post(API_URL, json=invoice_data, timeout=10)
        response.raise_for_status()
        print(f"✅ Invoice sent successfully: {response.status_code}")
        if response.text:
            print(f"Response: {response.text}")
        return response.json() if response.content else {"status": "success"}
    except requests.RequestException as e:
        print(f"❌ Failed to send invoice: {e}")
        raise
