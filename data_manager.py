# data_manager.py
# Saves and loads assessment records in a JSON file.
# Also finds old AI answers so the same input always gives the same result.

import hashlib
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

# Define a function to append and save a new assessment record into the persistent JSON storage file
def save_record(record, file_path=RECORDS_FILE):
    """Add one record to the file. Returns True if it was saved."""
    records = load_records(file_path)
    records.append(record)

    try:
        folder = os.path.dirname(file_path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(records, file, indent=2, ensure_ascii=False)
        return True
    except OSError:
        return False


# Define a helper function to extract the core deal details used for all input fingerprints
# Basically this is to avoid repeating the same code whenever you need to create an input fingerprint
def get_deal_parts(user_input):
    """The deal details used in every fingerprint."""
    return [
        user_input["chat"].strip().lower(),
        user_input["item"].strip().lower(),
        str(user_input["price"]),
        user_input["details"].strip().lower(),
    ]


# Define a function to generate a unique SHA-256 cryptographic hash fingerprint for Telegram link mode inputs
def make_input_key(user_input, messages):
    """Fingerprint for Telegram mode. Same deal + same messages -> same key."""
    parts = get_deal_parts(user_input)
    for message in messages:
        parts.append(message["text"])

    joined = "\n".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


# Define a function to generate a unique SHA-256 cryptographic hash fingerprint for screenshot upload mode inputs
def make_screenshot_key(user_input, image_paths):
    """Fingerprint for screenshot mode. Same deal + same images -> same key."""
    parts = get_deal_parts(user_input)
    for path in image_paths:
        with open(path, "rb") as file:
            parts.append(hashlib.sha256(file.read()).hexdigest())

    joined = "\n".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def find_saved_record(input_key, records):
    """Return the saved record for this input key, or None if not found."""
    for record in records:
        if record.get("input_key") == input_key:
            return record
    return None


def find_saved_ai_output(input_key, records):
    """Return the AI output saved for this input key, or None if not found."""
    record = find_saved_record(input_key, records)
    if record is None:
        return None
    return record.get("ai_output")


def filter_by_risk_level(records, risk_level):
    """Return only the records with this risk level, e.g. "High Risk"."""
    matching = []
    for record in records:
        if record.get("result", {}).get("risk_level") == risk_level:
            matching.append(record)
    return matching