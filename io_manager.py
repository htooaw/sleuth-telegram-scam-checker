def get_sender_name(telegram_message):
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