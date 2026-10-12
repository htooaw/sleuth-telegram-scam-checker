import os
import shlex
import math

from telethon.sync import TelegramClient

IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp", ".heic"]
SCREENSHOT_FOLDER = "data/screenshots"
MAX_SCREENSHOTS = 10
SESSION_FILE = "data/telegram"   # Telethon adds ".session"
MESSAGE_LIMIT = 50

def show_message(text: str) -> None:
    print(text)

def show_error(text: str) -> None:
    print("[Error] " + text)

def show_main_menu() -> str:
    """Print the menu and return the user's choice: "1", "2" or "3"."""
    print()
    print("=== Telegram Marketplace Risk Assessor (Buyer) ===")
    print("1. Check a new deal")
    print("2. View past checks")
    print("3. Exit")
    while True:
        choice = input("Choose 1-3: ").strip()
        if choice in ["1", "2", "3"]:
            return choice
        show_error("Please type 1, 2 or 3.")

def ask_text(label: str, required: bool = True) -> str:
    """Ask for text. If required, keep asking until it is not blank."""
    while True:
        answer = input(label + ": ").strip()
        if answer or not required:
            return answer
        show_error(label + " cannot be empty.")

def ask_price(label: str) -> float:
    """Ask for a price in SGD. Must be a number greater than 0."""
    while True:
        answer = input(label + ": ").strip().replace("$", "").replace(",", "")
        try:
            price = float(answer)
        except ValueError:
            show_error("Please type a number, e.g. 650 or 650.50")
            continue

        if not math.isfinite(price) or price <= 0:
            show_error("Price must be a number greater than 0.")
            continue
        return price


def ask_chat_source() -> str:
    """Ask where the chat comes from. Returns "telegram" or "screenshots"."""
    print()
    print("Read the chat from:")
    print("1. Telegram (log in to your account)")
    print("2. Screenshots (no login needed)")
    while True:
        choice = input("Choose 1-2: ").strip()
        if choice == "1":
            return "telegram"
        if choice == "2":
            return "screenshots"
        show_error("Please type 1 or 2.")


def is_image_file(path: str) -> bool:
    """Return True if the file name ends with an image extension we support."""
    return os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS

def find_screenshots_in_folder(folder: str = SCREENSHOT_FOLDER) -> list[str]:
    """Return all image files in the folder, sorted by file name."""
    if not os.path.isdir(folder):
        return []
    paths = []
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if os.path.isfile(path) and is_image_file(path):
            paths.append(path)
    return paths

def show_transcript(messages: list[dict]) -> None:
    """Show the chat the AI read from the screenshots, so the user can check it."""
    print()
    print("The AI read these messages from your screenshots:")
    for message in messages:
        line = " " + message["sender"] + ": " + message["text"]
        if message["date"]:
            line = " [" + message["date"] + "]" + line
        print(line)

def ask_screenshot_paths() -> tuple[list[str], str | None]:
    """Let the user drag screenshots into the terminal, or use the screenshots folder.
    Returns (paths, error)."""
    os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)
    print()
    print("Drag your screenshots into this window (in order), then press Enter.")
    print("Or just press Enter to use all images in the " + SCREENSHOT_FOLDER + "/ folder.")

    while True:
        answer = input("Screenshots: ").strip()

        if not answer:
            paths = find_screenshots_in_folder()
            if not paths:
                return [], "No images found in " + SCREENSHOT_FOLDER + "/. Put your screenshots there first."
        else:
            # Dragged paths are separated by spaces; shlex handles quotes and "\ " in names
            try:
                paths = shlex.split(answer)
            except ValueError:
                show_error("Could not understand those file paths. Please try again.")
                continue

            bad_path = None
            for path in paths:
                if not os.path.isfile(path) or not is_image_file(path):
                    bad_path = path
                    break
            if bad_path is not None:
                show_error("Not an image file I can open: " + bad_path)
                show_error("(Using Docker? Put the screenshots in " + SCREENSHOT_FOLDER
                           + "/ and just press Enter.)")
                continue

        if len(paths) > MAX_SCREENSHOTS:
            show_error("Please use at most " + str(MAX_SCREENSHOTS) + " screenshots.")
            if not answer:
                return [], "Too many images in " + SCREENSHOT_FOLDER + "/."
            continue

        print("Using " + str(len(paths)) + " screenshot(s):")
        for path in paths:
            print(" - " + os.path.basename(path))
        return paths, None

def get_deal_details(source: str) -> dict:
    """Ask the buyer about the deal they want to check."""
    print()
    if source == "telegram":
        print("Enter the seller's @username, or a t.me link to the group/channel.")
        chat = ask_text("Telegram chat")
    else:
        chat = ask_text("Seller name or handle (optional, press Enter to skip)", required=False)
        if not chat:
            chat = "Screenshots"
    item = ask_text("Item you are buying")
    price = ask_price("Agreed price (SGD)")
    details = ask_text("Extra details (optional, press Enter to skip)", required=False)
    return {"chat": chat, "item": item, "price": price, "details": details}
def get_sender_name(telegram_message: object) -> str:
    """Return a readable name for who sent a Telegram message."""
    if telegram_message.out:
        return "You"
    sender = telegram_message.sender
    if sender is None:
        return "Unknown"
    if getattr(sender, "username", None):
        return "@" + sender.username
    if getattr(sender, "first_name", None):
        return sender.first_name
    if getattr(sender, "title", None):
        return sender.title
    return "Unknown"

def fetch_chat_messages(chat: str) -> tuple[list[dict], str | None]:
    """Log in to Telegram and read the last messages of one chat.
    Returns (messages, error). messages are oldest first."""
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    if not api_id or not api_hash:
        return [], "TELEGRAM_API_ID or TELEGRAM_API_HASH is missing from the .env file."
    if not api_id.isdigit():
        return [], "TELEGRAM_API_ID must be a number."

    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    print("Connecting to Telegram... (the first time, it will ask for your phone number and a login code)")

    try:
        with TelegramClient(SESSION_FILE, int(api_id), api_hash) as client:
            entity = client.get_entity(chat)
            telegram_messages = client.get_messages(entity, limit=MESSAGE_LIMIT)
    except Exception as error:  # wrong username, no internet, login cancelled...
        return [], "Could not read this chat: " + str(error)

    messages = []
    for telegram_message in telegram_messages:
        if not telegram_message.message:   # skip photos/stickers without text
            continue
        messages.append({
            "sender": get_sender_name(telegram_message),
            "date": telegram_message.date.strftime("%Y-%m-%d %H:%M"),
            "text": telegram_message.message,
        })

    messages.reverse()   # Telegram gives newest first; we want oldest first
    if not messages:
        return [], "This chat has no text messages to check."
    return messages, None

# Shown when the AI feedback could not be generated
FALLBACK_ADVICE = {
    "High Risk": "Do not pay. Stop the deal or insist on meeting in person.",
    "Medium Risk": "Be careful. Ask for the missing details and avoid paying in advance.",
    "Low Risk": "No major warning signs. Still use a safe payment method.",
}

def display_result(record: dict) -> None:
    """Print the score, the AI feedback and the warning signs of one check."""
    result = record["result"]
    print()
    print("=" * 60)
    print("RESULT")
    print("=" * 60)
    print("Risk score: " + str(result["score"]) + " / " + str(result["max_score"])
          + " (" + result["risk_level"] + ")")
    if record["from_saved"]:
        print("(Same chat and details as before - reused the saved AI answer.)")

    feedback = record.get("feedback")
    if feedback:
        print()
        print("What this means:")
        print(feedback["feedback"])
        if feedback["next_steps"]:
            print()
            print("What to do next:")
            for step in feedback["next_steps"]:
                print(" - " + step)
    else:
        print()
        print("What to do: " + FALLBACK_ADVICE[result["risk_level"]])

    if result["risk_factors"]:
        print()
        print("Warning signs:")
        for factor in result["risk_factors"]:
            print(" - " + factor)

    if result["missing_information"]:
        print()
        print("Missing information:")
        for item in result["missing_information"]:
            print(" - " + item)

    if result["evidence"]:
        print()
        print("Evidence from the chat:")
        for quote in result["evidence"]:
            print(" - " + quote)

    print()
    print("Note: this is advice to help you decide, not proof that someone is a scammer.")
    print("=" * 60)

def ask_history_filter() -> str | None:
    print()
    print("Show which checks?")
    print("1. All")
    print("2. High Risk only")
    print("3. Medium Risk only")
    print("4. Low Risk only")
    while True:
        choice = input("Choose 1-4: ").strip()
        if choice == "1":
            return None              # None means "show everything"
        if choice == "2":
            return "High Risk"
        if choice == "3":
            return "Medium Risk"
        if choice == "4":
            return "Low Risk"
        show_error("Please type 1, 2, 3 or 4.")


def display_history(records: list[dict]) -> None:
    print()
    if not records:
        print("No matching past checks.")
        return

    print("Past checks:")
    number = 1
    for record in records:
        deal = record["input"]
        print(str(number) + ". " + record["time"] + " | " + deal["chat"] + " | "
              + deal["item"] + " | SGD " + format(deal["price"], ".2f") + " | "
              + record["result"]["risk_level"])
        number += 1