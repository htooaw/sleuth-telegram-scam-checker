# main.py
# Command-line version of the Telegram Marketplace Risk Assessor.
# Same steps as the web app: read the chat, AI analysis, risk score, AI feedback, save.

import logging
import os
from datetime import datetime

from dotenv import load_dotenv

import ai_manager
import data_manager
import io_manager
import logic_manager

LOG_FILE = "data/app.log"


def run_check(user_input: dict, messages: list[dict], records: list[dict], input_key: str, source: str) -> dict | None:
    """Analyse one deal and return its record, or None if the AI analysis failed."""
    # Same input as before? Reuse the saved AI answer so the result is the same.
    saved_record = data_manager.find_saved_record(input_key, records)
    if saved_record is not None:
        ai_output = saved_record["ai_output"]
        messages = saved_record.get("messages", messages)
        from_saved = True
    else:
        ai_result = ai_manager.analyze_chat(user_input, messages)
        if not ai_result["ok"]:
            io_manager.show_error("AI analysis failed: " + ai_result["error"])
            return None
        ai_output = ai_result["data"]
        from_saved = False

    # The logic manager decides the score, the AI only explains it
    result = logic_manager.evaluate_risk(ai_output)

    feedback = saved_record.get("feedback") if saved_record is not None else None
    if feedback is None:
        io_manager.show_message("Writing feedback (AI stage 3)...")
        feedback_result = ai_manager.generate_feedback(user_input, ai_output, result)
        if feedback_result["ok"]:
            feedback = feedback_result["data"]
        else:
            io_manager.show_error("AI feedback is not available right now: " + feedback_result["error"])

    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": source,
        "input_key": input_key,
        "input": user_input,
        "message_count": len(messages),
        "messages": messages,
        "ai_output": ai_output,
        "result": result,
        "feedback": feedback,
        "from_saved": from_saved,
    }

    # Only save new answers (reused ones are already in the file)
    if not from_saved:
        if data_manager.save_record(record):
            records.append(record)
        else:
            io_manager.show_error("Could not save this check to the records file.")

    return record


def get_telegram_messages(user_input: dict) -> tuple[list[dict] | None, str | None]:
    """Telegram mode: read the chat. Returns (messages, input_key) or (None, None)."""
    messages, error = io_manager.fetch_chat_messages(user_input["chat"])
    if error:
        io_manager.show_error(error)
        return None, None

    io_manager.show_message("Read " + str(len(messages)) + " messages. Asking the AI...")
    return messages, data_manager.make_input_key(user_input, messages)


def get_screenshot_messages(user_input: dict, records: list[dict]) -> tuple[list[dict] | None, str | None]:
    """Screenshot mode: AI stage 1 reads the images. Returns (messages, input_key) or (None, None)."""
    image_paths, error = io_manager.ask_screenshot_paths()
    if error:
        io_manager.show_error(error)
        return None, None

    input_key = data_manager.make_screenshot_key(user_input, image_paths)

    # Same screenshots checked before? Skip stage 1 - run_check reuses the saved chat.
    if data_manager.find_saved_record(input_key, records) is not None:
        return [], input_key

    io_manager.show_message("Reading the screenshots with AI (stage 1 of 3)...")
    extraction = ai_manager.read_screenshots(image_paths)
    if not extraction["ok"]:
        io_manager.show_error("Could not read the screenshots: " + extraction["error"])
        return None, None

    messages = extraction["data"]
    io_manager.show_transcript(messages)
    io_manager.show_message("Checking the chat for warning signs (stage 2 of 3)...")
    return messages, input_key


def check_new_deal(records: list[dict]) -> None:
    """Menu option 1: check a new deal."""
    source = io_manager.ask_chat_source()
    user_input = io_manager.get_deal_details(source)

    if source == "telegram":
        messages, input_key = get_telegram_messages(user_input)
    else:
        messages, input_key = get_screenshot_messages(user_input, records)

    if messages is None:
        return

    record = run_check(user_input, messages, records, input_key, source)
    if record is not None:
        io_manager.display_result(record)


def view_past_checks(records: list[dict]) -> None:
    """Menu option 2: list past checks, optionally only one risk level."""
    risk_level = io_manager.ask_history_filter()
    if risk_level is None:
        io_manager.display_history(records)
    else:
        io_manager.display_history(data_manager.filter_by_risk_level(records, risk_level))


def main() -> None:
    load_dotenv()

    # Write warnings (e.g. AI failures) to a log file
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    logging.basicConfig(filename=LOG_FILE, level=logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")

    # Load all past checks once at startup
    records = data_manager.load_records()
    io_manager.show_message("Loaded " + str(len(records)) + " past checks.")

    try:
        while True:
            choice = io_manager.show_main_menu()
            if choice == "1":
                check_new_deal(records)
            elif choice == "2":
                view_past_checks(records)
            else:
                break
    except (KeyboardInterrupt, EOFError):
        pass
    io_manager.show_message("Goodbye.")


if __name__ == "__main__":
    main()
