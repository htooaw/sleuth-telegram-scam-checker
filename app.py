import streamlit as st
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telethon import TelegramClient

import ai_manager
import data_manager
import logic_manager
import io_manager

# Load environment variables
load_dotenv()

# Use the same login file as io_manager, so logging in here lets fetch_chat_messages read chats
SESSION_NAME = io_manager.SESSION_FILE
API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")

SCREENSHOT_FOLDER = io_manager.SCREENSHOT_FOLDER

# Shown when the AI feedback could not be generated
FALLBACK_ADVICE = {
    "High Risk": "Do not pay. Stop the deal or insist on meeting in person.",
    "Medium Risk": "Be careful. Ask for the missing details and avoid paying in advance.",
    "Low Risk": "No major warning signs. Still use a safe payment method.",
}

# Initialize records in session state
if "records" not in st.session_state:
    st.session_state.records = data_manager.load_records()

os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)

# UI: Page Configuration & Theme
st.set_page_config(
    page_title="Telegram Risk Assessor",
    layout="centered"
)

# --- CSS STYLING ---
st.markdown("""
<style>
    /* Main container styling */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Modernize buttons */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: bold;
        background-color: #ff4b4b;
        color: white;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #e03e3e;
        border-color: #e03e3e;
    }

    /* Headers */
    h1 {
        color: #1f2937;
        font-weight: 800;
    }
</style>
""", unsafe_allow_html=True)


def run_async(coro):
    """Helper to run async Telethon functions inside Streamlit"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

async def check_auth():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()
    is_auth = await client.is_user_authorized()
    await client.disconnect()
    return is_auth


def show_telegram_login():
    """Sidebar login. Only shown in Telegram username mode."""
    with st.sidebar:
        st.title("Telegram Login")
        st.markdown("---")

        if "tg_authenticated" not in st.session_state:
            try:
                st.session_state.tg_authenticated = run_async(check_auth())
            except Exception:
                st.session_state.tg_authenticated = False

        if st.session_state.tg_authenticated:
            st.success("Logged in securely")
            return

        st.warning("Not logged in")
        phone = st.text_input("Phone Number (e.g., +65...):")

        if "phone_hash" not in st.session_state:
            if st.button("Send Login Code"):
                async def send_code():
                    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
                    await client.connect()
                    res = await client.send_code_request(phone)
                    await client.disconnect()
                    return res.phone_code_hash

                try:
                    st.session_state.phone_hash = run_async(send_code())
                    st.session_state.phone_number = phone
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")
        else:
            code = st.text_input("Enter 5-digit Telegram Code:")
            if st.button("Complete Login"):
                async def submit_code():
                    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
                    await client.connect()
                    await client.sign_in(phone=st.session_state.phone_number, code=code, phone_code_hash=st.session_state.phone_hash)
                    await client.disconnect()

                try:
                    run_async(submit_code())
                    st.session_state.tg_authenticated = True
                    del st.session_state["phone_hash"]
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")


def get_messages(source, user_input, uploaded_files):
    """Read the chat for the chosen mode. Returns (messages, input_key) or (None, None)."""
    if source == "Telegram username":
        # Telethon needs an event loop in this thread
        asyncio.set_event_loop(asyncio.new_event_loop())
        messages, error = io_manager.fetch_chat_messages(user_input["chat"])
        if error:
            st.error(f"Failed to read chat: {error}")
            return None, None
        return messages, data_manager.make_input_key(user_input, messages)

    # Screenshot mode: save the uploads, then AI stage 1 reads them
    for old_file in os.listdir(SCREENSHOT_FOLDER):
        os.remove(os.path.join(SCREENSHOT_FOLDER, old_file))

    image_paths = []
    for f in uploaded_files:
        path = os.path.join(SCREENSHOT_FOLDER, f.name)
        with open(path, "wb") as disk_file:
            disk_file.write(f.getbuffer())
        image_paths.append(path)

    input_key = data_manager.make_screenshot_key(user_input, image_paths)

    # Same screenshots checked before? Skip stage 1 and reuse the saved chat
    if data_manager.find_saved_record(input_key, st.session_state.records) is not None:
        return [], input_key

    extraction = ai_manager.read_screenshots(image_paths)
    if not extraction["ok"]:
        st.error(f"Could not read screenshots: {extraction['error']}")
        return None, None
    return extraction["data"], input_key


def run_assessment(source, user_input, messages, input_key):
    """AI stage 2 + score + AI stage 3. Returns the record, or None if the AI failed."""
    saved_record = data_manager.find_saved_record(input_key, st.session_state.records)
    if saved_record is not None:
        ai_result = {"ok": True, "data": saved_record["ai_output"]}
        messages = saved_record.get("messages", messages)
        from_saved = True
    else:
        ai_result = ai_manager.analyze_chat(user_input, messages)
        from_saved = False

    if not ai_result["ok"]:
        st.error(f"AI Analysis Failed: {ai_result.get('error', 'Unknown error')}")
        return None

    # The logic manager decides the score, the AI only explains it
    result = logic_manager.evaluate_risk(ai_result["data"])

    feedback = saved_record.get("feedback") if saved_record is not None else None
    if feedback is None:
        feedback_result = ai_manager.generate_feedback(user_input, ai_result["data"], result)
        if feedback_result["ok"]:
            feedback = feedback_result["data"]
        else:
            st.warning("AI feedback is not available right now: " + feedback_result["error"])

    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": source,
        "input_key": input_key,
        "input": user_input,
        "message_count": len(messages),
        "messages": messages,
        "ai_output": ai_result["data"],
        "result": result,
        "feedback": feedback,
        "from_saved": from_saved,
    }

    if not from_saved:
        if data_manager.save_record(record):
            st.session_state.records.append(record)
        else:
            st.error("Could not save this check to the records file.")

    return record


def show_result(record):
    """Show the score, the AI feedback and the warning signs."""
    result = record["result"]
    score = result.get("score", 0)
    max_score = result.get("max_score", logic_manager.MAX_SCORE)
    risk_level = result["risk_level"]

    st.markdown("### Final Risk Report")
    message = f"**Risk score: {score} / {max_score} ({risk_level})**"
    if risk_level == "High Risk":
        st.error(message)
    elif risk_level == "Medium Risk":
        st.warning(message)
    else:
        st.success(message)
    st.progress(score / max_score)

    if record.get("from_saved"):
        st.caption("Same chat and details as before - reused the saved AI analysis.")

    feedback = record.get("feedback")
    if feedback:
        st.markdown("#### What this means")
        st.write(feedback["feedback"])
        if feedback["next_steps"]:
            st.markdown("#### What to do next")
            for step in feedback["next_steps"]:
                st.markdown(f"- {step}")
    else:
        st.info(f"**Recommended Action:** {FALLBACK_ADVICE[risk_level]}")

    if result.get("risk_factors"):
        st.markdown("#### Warning Signs Found")
        for factor in result["risk_factors"]:
            st.markdown(f"- {factor}")

    if result.get("missing_information"):
        st.markdown("#### Missing Information")
        for info in result["missing_information"]:
            st.markdown(f"- {info}")

    if result.get("evidence"):
        st.markdown("#### Evidence From the Chat")
        for quote in result["evidence"]:
            st.markdown(f"- {quote}")

    # Show the chat the AI read, so the user can spot anything it misread
    messages = record.get("messages", [])
    if messages:
        with st.expander(f"Messages the AI read ({len(messages)})"):
            for message in messages:
                text = message["text"].replace("$", "\\$")   # stop "$" being shown as maths
                line = f"**{message['sender']}:** {text}"
                if message["date"]:
                    line = f"`{message['date']}` " + line
                st.markdown(line)

    st.caption("This is advice to help you decide, not proof that someone is a scammer.")


def show_new_check():
    """Page 1: check a new deal, from screenshots or a Telegram username."""
    source = st.radio("How do you want to share the chat?", ["Screenshots", "Telegram username"], horizontal=True)

    # Only the username mode needs a Telegram login
    if source == "Telegram username":
        show_telegram_login()

    # Each mode needs just one input: the screenshots, or the seller's username
    uploaded_files = []
    if source == "Screenshots":
        chat = "Screenshots"
        uploaded_files = st.file_uploader("Drag and drop chat screenshots here", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
    else:
        chat = st.text_input("Seller's Telegram @username or link:", placeholder="@seller_admin").strip()

    # The AI works out the item and price from the chat itself
    user_input = {"chat": chat, "item": "", "price": 0.0, "details": ""}

    st.markdown("---")

    if not st.button("Assess Deal Risk", use_container_width=True):
        return

    if source == "Telegram username" and not st.session_state.get("tg_authenticated"):
        st.error("Please log in to Telegram in the sidebar first.")
    elif source == "Telegram username" and not user_input["chat"]:
        st.error("Please enter the seller's Telegram @username or link.")
    elif source == "Screenshots" and not uploaded_files:
        st.error("Please upload at least one screenshot.")
    else:
        with st.spinner("Analysing the chat..."):
            messages, input_key = get_messages(source, user_input, uploaded_files)
            record = None
            if messages is not None:
                record = run_assessment(source, user_input, messages, input_key)
        if record is not None:
            show_result(record)


def show_past_checks():
    """Page 2: list the saved checks, newest first, with a risk level filter."""
    choice = st.selectbox("Show which checks?", ["All", "High Risk", "Medium Risk", "Low Risk"])
    if choice == "All":
        records = st.session_state.records
    else:
        records = data_manager.filter_by_risk_level(st.session_state.records, choice)

    if not records:
        st.info("No matching past checks.")
        return

    for record in reversed(records):
        deal = record["input"]
        result = record["result"]
        score = result.get("score")
        score_text = f"{score}/{result.get('max_score', logic_manager.MAX_SCORE)}" if score is not None else "no score"
        what = deal.get("item") or record.get("ai_output", {}).get("transaction_summary", "")
        title = f"{record['time']} | {deal['chat']} | {what[:60]} | {result['risk_level']} ({score_text})"
        with st.expander(title):
            st.write(f"**Seller / chat:** {deal['chat']}")
            feedback = record.get("feedback")
            if feedback:
                st.write(feedback["feedback"])
            for factor in result.get("risk_factors", []):
                st.markdown(f"- {factor}")


# ==========================================
# MAIN PAGE
# ==========================================
st.title("Telegram Risk Assessor")
st.markdown("Protect your online marketplace transactions with real-time AI behavioral analysis.")
st.markdown("---")

page = st.radio("What would you like to do?", ["Check a new deal", "View past checks"], horizontal=True)
st.markdown("---")

if page == "Check a new deal":
    show_new_check()
else:
    show_past_checks()
