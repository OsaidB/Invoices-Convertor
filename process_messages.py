# File: process_messages.py
import re
import os
import requests
from convert_invoice import process_invoice_pdf
import charset_normalizer

# Step 1: Read the text file and extract relevant rows
def read_and_filter_text_file(text_file_path):
    # Detect the file encoding
    with open(text_file_path, "rb") as f:
        raw_data = f.read()
        result = charset_normalizer.detect(raw_data)
        encoding = result['encoding']
        print(f"Detected encoding: {encoding}")

    invoice_urls = []
    with open(text_file_path, "r", encoding=encoding) as f:
        for line_number, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            print(f"Processing line {line_number}: '{line}'")
            # Match Row: <number> followed by key=value pairs, capturing address and body
            match = re.search(r"Row:\s*\d+\s*.*address=([^,]+),\s*.*body=([^,]+)", line)
            if match:
                address = match.group(1).strip()
                body = match.group(2).strip()
                print(f"Parsed: address='{address}', body='{body}'")
                # Filter for AL-Eatimad messages with specific URLs
                if address == "AL-Eatimad" and body.startswith("http://188.34.164.0/openpdf/report"):
                    invoice_urls.append(body)
                    print(f"Matched URL: {body}")
    return invoice_urls

# Step 2: Download the PDF files
def download_pdf(url, output_path):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise an error for bad status codes
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"Downloaded PDF: {output_path}")
        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False

# Main processing logic
def main():
    text_file_path = "messages.txt"  # Path to your text file
    invoice_urls = read_and_filter_text_file(text_file_path)
    print(f"Found {len(invoice_urls)} invoice URLs: {invoice_urls}")

    # Create output directories if they don't exist
    os.makedirs("pdfs", exist_ok=True)
    os.makedirs("jsons", exist_ok=True)

    # Download and process each PDF
    for idx, url in enumerate(invoice_urls):
        # Generate PDF name based on index initially (will be renamed by date)
        pdf_path = os.path.join("pdfs", f"temp_invoice_{idx}.pdf")
        if not download_pdf(url, pdf_path):
            continue  # Skip if download fails

        # Process the PDF using the function from convert_invoice.py
        try:
            invoice_data = process_invoice_pdf(pdf_path, "pdfs", "jsons")

            # Use the extracted date to rename the PDF
            if invoice_data["date"]:
                date_str = invoice_data["date"].replace("/", "-").replace(" ", "_").replace(":", "")
                final_pdf_path = os.path.join("pdfs", f"{date_str}.pdf")
                final_json_path = os.path.join("jsons", f"{date_str}.json")

                # Ensure unique filenames by appending index if file exists
                pdf_base, pdf_ext = os.path.splitext(final_pdf_path)
                json_base, json_ext = os.path.splitext(final_json_path)
                pdf_index = 0
                while os.path.exists(final_pdf_path):
                    final_pdf_path = f"{pdf_base}_{pdf_index}{pdf_ext}"
                    pdf_index += 1
                json_index = 0
                while os.path.exists(final_json_path):
                    final_json_path = f"{json_base}_{json_index}{json_ext}"
                    json_index += 1

                # Rename the temporary PDF to the final name
                os.rename(pdf_path, final_pdf_path)
                print(f"Renamed PDF to: {final_pdf_path}")
            else:
                print(f"No date extracted for {pdf_path}, keeping temporary PDF name")

            # The JSON is already saved with the date-based name by process_invoice_pdf
            print(f"JSON saved as: {final_json_path if invoice_data['date'] else 'default_name_in_jsons'}")

            # Log the result
            print(f"Processed invoice data for {pdf_path}: {invoice_data}")

        except Exception as e:
            print(f"Failed to process {pdf_path}: {e}")
            print(f"Preserving PDF due to error: {pdf_path}")
            continue

if __name__ == "__main__":
    main()