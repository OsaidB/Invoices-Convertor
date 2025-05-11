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

    # Download and process each PDF
    for idx, url in enumerate(invoice_urls):
        # Download the PDF
        pdf_path = f"invoice_{idx}.pdf"
        if not download_pdf(url, pdf_path):
            continue  # Skip if download fails

        # Process the PDF using the function from convert_invoice.py
        try:
            invoice_data = process_invoice_pdf(pdf_path)

            # The JSON is already saved by process_invoice_pdf, but we can log the result
            print(f"Processed invoice data for {pdf_path}: {invoice_data}")

            # Remove the temporary PDF file to save space
            os.remove(pdf_path)
            print(f"Removed temporary PDF: {pdf_path}")

        except Exception as e:
            print(f"Failed to process {pdf_path}: {e}")

if __name__ == "__main__":
    main()