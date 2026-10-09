import os

IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp", ".heic"]
SCREENSHOT_FOLDER = "data/screenshots"

def show_message(text):
    print(text)

def show_error(text):
    print("[Error] " + text)

def show_main_menu():
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

def is_image_file(path):
    """Return True if the file name ends with an image extension we support."""
    return os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS

def find_screenshots_in_folder(folder=SCREENSHOT_FOLDER):
    """Return all image files in the folder, sorted by file name."""
    if not os.path.isdir(folder):
        return []
    paths = []
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if os.path.isfile(path) and is_image_file(path):
            paths.append(path)
    return paths

def show_transcript(messages):
    """Show the chat the AI read from the screenshots, so the user can check it."""
    print()
    print("The AI read these messages from your screenshots:")
    for message in messages:
        line = " " + message["sender"] + ": " + message["text"]
        if message["date"]:
            line = " [" + message["date"] + "]" + line
        print(line)


