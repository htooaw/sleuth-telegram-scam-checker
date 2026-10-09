



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

        