import json
from dotenv import load_dotenv
import io_manager
import ai_manager
import logic_manager
import data_manager

def run_app():
    load_dotenv()

    # 1. Collect inputs
    user_data = io_manager.get_user_input()

    # 2. Scrape Telegram channel history
    print("\nFetching channel message history via Telethon...")
    chat_history = io_manager.fetch_channel_messages(user_data["group_link"])  

    # 3. Analyze with Gemini
    ai_res = ai_manager.analyze_transaction_risk(user_data, chat_history)      