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

    cleaned_res = ai_res
    if isinstance(ai_res, str):
        cleaned_res = ai_res.strip()
        if cleaned_res.startswith("```json"):
            cleaned_res = cleaned_res[7:]
        if cleaned_res.startswith("```"):
            cleaned_res = cleaned_res[3:]
        if cleaned_res.endswith("```"):
            cleaned_res = cleaned_res[:-3]
        
        try:
            ai_parsed = json.loads(cleaned_res.strip())
        except Exception as e:
            ai_parsed = {"error": f"JSON parse error: {e}"}
    else:
        ai_parsed = ai_res

    if "error" in ai_parsed:
        print(f"\n[Error]: {ai_parsed['error']}")
        return
      