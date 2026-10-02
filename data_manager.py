# data_manager.py

import json
import os

RECORDS_FILE = "data/records.json"

# Define a function to load and return all saved assessment records from the storage file
def load_records(file_path=RECORDS_FILE):
    """Return the list of saved records. Missing or broken file -> empty list."""
    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            records = json.load(file)
    except (json.JSONDecodeError, OSError):
        return []

    # The file must contain a list of records
    if not isinstance(records, list):
        return []
    return records

