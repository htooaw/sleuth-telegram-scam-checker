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