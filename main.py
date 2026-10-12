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

    # 4. Evaluate risk & save
    result = logic_manager.evaluate_risk(user_data, ai_parsed)
    data_manager.save_record({"input": user_data, "result": result})
    
     # 5. Display result
    io_manager.display_result(result)

if __name__ == "__main__":
    run_app()     