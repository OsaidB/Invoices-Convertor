#move_mismatched_invoices.py

import os
import json
import shutil

# Base directories
base_dir = os.path.dirname(os.path.abspath(__file__))
correct_dir = os.path.join(base_dir, 'jsons', 'correctly matched')
mismatched_base_dir = os.path.join(base_dir, 'jsons', 'mismatched')

# Traverse year-based subdirectories
for year_folder in os.listdir(correct_dir):
    year_path = os.path.join(correct_dir, year_folder)

    if not os.path.isdir(year_path):
        continue

    for file in os.listdir(year_path):
        if not file.endswith('.json'):
            continue

        file_path = os.path.join(year_path, file)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Failed to parse JSON: {file}")
            continue

        if data.get("total_match") is False:
            # Mismatch: move to mismatched/<year>/
            target_dir = os.path.join(mismatched_base_dir, year_folder)
            os.makedirs(target_dir, exist_ok=True)
            shutil.move(file_path, os.path.join(target_dir, file))
            print(f"❌ Mismatch found: {file}")
        else:
            print(f"✅ Matched: {file}")
