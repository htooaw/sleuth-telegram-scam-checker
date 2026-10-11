def fetch_chat_messages(chat):
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
