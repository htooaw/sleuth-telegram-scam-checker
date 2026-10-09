
def get_deal_details(source):
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

