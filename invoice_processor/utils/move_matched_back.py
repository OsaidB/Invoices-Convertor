# move_matched_back.py

import os
import json
import shutil

def move_matched_back():
    # Base directories
    base_dir = os.path.dirname(os.path.abspath(__file__))
    mismatched_base_dir = os.path.join(base_dir, 'jsons', 'mismatched')
    correct_dir = os.path.join(base_dir, 'jsons', 'correctly matched')

    # Traverse year-based subdirectories
    for year_folder in os.listdir(mismatched_base_dir):
        year_path = os.path.join(mismatched_base_dir, year_folder)

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

            if data.get("total_match") is True:
                # Matched: move to correctly matched/<year>/
                target_dir = os.path.join(correct_dir, year_folder)
                os.makedirs(target_dir, exist_ok=True)
                shutil.move(file_path, os.path.join(target_dir, file))
                print(f"✅ Matched (moved back): {file}")
            else:
                print(f"❌ Still mismatched: {file}")
