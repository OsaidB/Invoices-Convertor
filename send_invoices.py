import json
import os
import requests

def send_invoices_to_api(json_base_dir="jsons"):
    """
    Read JSON invoice files from jsons/matched and jsons/mismatched directories
    (including subdirectories like 2024, 2025) and send each as a POST request
    to http://localhost:8080/api/invoices.
    """
    # Define the API endpoint
    api_url = "http://localhost:8080/api/invoices"

    # Ensure the base directory exists
    if not os.path.exists(json_base_dir):
        print(f"Directory {json_base_dir} not found.")
        return

    # Define the subdirectories to process
    target_dirs = [os.path.join(json_base_dir, "currectlly matched"), os.path.join(json_base_dir, "mismatched")]

    # Iterate over matched and mismatched directories
    for target_dir in target_dirs:
        if not os.path.exists(target_dir):
            print(f"Directory {target_dir} not found, skipping...")
            continue

        # Recursively walk through the directory (e.g., matched/2024, mismatched/2025)
        for root, dirs, files in os.walk(target_dir):
            for filename in files:
                if filename.endswith(".json"):
                    json_path = os.path.join(root, filename)
                    print(f"Processing {json_path}")

                    # Read the JSON file
                    try:
                        with open(json_path, "r", encoding="utf-8") as f:
                            invoice_data = json.load(f)
                    except Exception as e:
                        print(f"Failed to read {json_path}: {e}")
                        continue

                    # Send the JSON data to the API
                    try:
                        response = requests.post(api_url, json=invoice_data, timeout=10)
                        response.raise_for_status()  # Raise an error for bad status codes
                        print(f"Successfully sent {json_path} to API. Status code: {response.status_code}")
                        if response.text:
                            print(f"Response: {response.text}")
                    except requests.exceptions.RequestException as e:
                        print(f"Failed to send {json_path} to API: {e}")

if __name__ == "__main__":
    send_invoices_to_api()