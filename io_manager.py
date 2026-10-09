import os
import shlex

IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp", ".heic"]
SCREENSHOT_FOLDER = "data/screenshots"
MAX_SCREENSHOTS = 10


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
        
def ask_chat_source():

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

def ask_screenshot_paths():
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
