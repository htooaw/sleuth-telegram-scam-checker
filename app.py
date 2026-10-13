import asyncio
import os
import tempfile
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
from telethon import TelegramClient

import ai_manager
import data_manager
import io_manager
import logic_manager

# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

# Use the same Telegram session file as io_manager so that authentication here can be reused when fetching Telegram chats
SESSION_NAME = io_manager.SESSION_FILE

API_HASH = os.environ.get("TELEGRAM_API_HASH", "").strip()

SCREENSHOT_FOLDER = io_manager.SCREENSHOT_FOLDER

ALLOWED_IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp"}

# Shown when AI-generated feedback is unavailable
FALLBACK_ADVICE = {
    "High Risk": (
        "Do not pay. Stop the deal or insist on meeting in person."
    ),
    "Medium Risk": (
        "Be careful. Ask for the missing details and avoid paying in advance."
    ),
    "Low Risk": (
        "No major warning signs were identified. Still use a safe payment method."
    ),
}

# Streamlit requires set_page_config() to be called before any other Streamlit command
st.set_page_config(
    page_title="Telegram Risk Assessor",
    layout="centered",
)

# ============================================================
# INITIALISATION
# ============================================================

if "records" not in st.session_state:
    st.session_state.records = data_manager.load_records()

os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)

# ============================================================
# CSS STYLING
# ============================================================

st.markdown(
    """
    <style>
        /* Main container styling */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        .stButton>button {
            width: 100%;
            border-radius: 8px;
            font-weight: bold;
            background-color: #ff4b4b;
            color: white;
            transition: all 0.3s ease;
            height: 100%;
            width: 100%;
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

        /* Vertical alignment for columns */
        [data-testid="stHorizontalBlock"]
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# TELEGRAM HELPERS
# ============================================================

def run_async(coro):
    """Run an asynchronous operation using a dedicated event loop."""
    loop = asyncio.new_event_loop()

    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(None)

def create_telegram_client():
    """Create a Telegram client after validating the API credentials."""
    api_id_value = os.environ.get("TELEGRAM_API_ID", "").strip()

    try:
        api_id = int(api_id_value)
    except (TypeError, ValueError):
        raise ValueError(
            "TELEGRAM_API_ID is missing or invalid. "
            "Check your Telegram API credentials in the environment."
        )

    if api_id <= 0 or not API_HASH:
        raise ValueError(
            "Telegram API credentials are missing. "
            "Please configure TELEGRAM_API_ID and TELEGRAM_API_HASH."
        )

    return TelegramClient(SESSION_NAME, api_id, API_HASH)

async def check_auth():
    """Check whether the existing Telegram session is authorised."""
    client = create_telegram_client()

    try:
        await client.connect()
        return await client.is_user_authorized()
    finally:
        if client.is_connected():
            await client.disconnect()

def render_inline_telegram_login():
    """Render the Telegram login flow inside the username input mode."""

    # Check the existing session only once per Streamlit session, unless the authentication state is explicitly reset
    if "tg_authenticated" not in st.session_state:
        try:
            st.session_state.tg_authenticated = run_async(check_auth())
        except Exception:
            st.session_state.tg_authenticated = False

    if not st.session_state.tg_authenticated:
        st.info(
            "🔐 **Authentication Required:** "
            "Please log in to Telegram to fetch live chat messages."
        )

        phone = st.text_input(
            "Phone Number (e.g., +65...):",
            key="telegram_phone_input",
        ).strip()

        # Step 1: Request a Telegram login code
        if "phone_hash" not in st.session_state:
            if st.button("Send Login Code"):
                if not phone:
                    st.error("Please enter your phone number.")
                else:

                    async def send_code():
                        client = create_telegram_client()

                        try:
                            await client.connect()
                            response = await client.send_code_request(phone)
                            return response.phone_code_hash
                        finally:
                            if client.is_connected():
                                await client.disconnect()

                    try:
                        st.session_state.phone_hash = run_async(send_code())
                        st.session_state.phone_number = phone
                        st.rerun()
                    except Exception as exc:
                        st.error(
                            "Failed to send the Telegram login code: "
                            f"{exc}"
                        )

        # Step 2: Submit the login code
        else:
            code = st.text_input(
                "Enter Telegram Login Code:",
                key="telegram_login_code",
            ).strip()

            col_a, col_b = st.columns([2, 1])

            with col_a:
                if st.button("Complete Login"):
                    if not code:
                        st.error("Please enter the login code.")
                    else:

                        async def submit_code():
                            client = create_telegram_client()

                            try:
                                await client.connect()

                                await client.sign_in(
                                    phone=st.session_state.phone_number,
                                    code=code,
                                    phone_code_hash=st.session_state.phone_hash,
                                )
                            finally:
                                if client.is_connected():
                                    await client.disconnect()

                        try:
                            run_async(submit_code())

                            st.session_state.tg_authenticated = True
                            st.session_state.pop("phone_hash", None)
                            st.session_state.pop("phone_number", None)

                            st.rerun()

                        except Exception as exc:
                            st.error(f"Telegram login failed: {exc}")

            with col_b:
                if st.button("Cancel"):
                    st.session_state.pop("phone_hash", None)
                    st.session_state.pop("phone_number", None)
                    st.rerun()

    else:
        auth_col1, auth_col2 = st.columns([4, 1])

        with auth_col1:
            st.success("✅ Authenticated with Telegram")

        with auth_col2:
            if st.button("Log Out"):
                # Reset the UI authentication state.
                st.session_state.tg_authenticated = False
                st.session_state.pop("phone_hash", None)
                st.session_state.pop("phone_number", None)
                st.rerun()

# ============================================================
# INPUT RETRIEVAL
# ============================================================

def get_messages(source, user_input, uploaded_files):
    """
    Retrieve messages from the selected source.

    Returns:
        (messages, input_key) on success.
        (None, None) if retrieval or screenshot extraction fails.
    """

    # --------------------------------------------------------
    # Telegram username mode
    # --------------------------------------------------------

    if source == "Telegram username":
        loop = asyncio.new_event_loop()

        try:
            asyncio.set_event_loop(loop)

            messages, error = io_manager.fetch_chat_messages(
                user_input["chat"]
            )

        except Exception as exc:
            st.error(f"Failed to read Telegram chat: {exc}")
            return None, None

        finally:
            loop.close()
            asyncio.set_event_loop(None)

        if error:
            st.error(f"Failed to read Telegram chat: {error}")
            return None, None

        if not isinstance(messages, list):
            st.error("Telegram returned an unexpected message format.")
            return None, None

        input_key = data_manager.make_input_key(user_input, messages)

        return messages, input_key

    # --------------------------------------------------------
    # Screenshot mode
    # --------------------------------------------------------

    # Keep track only of files created for this assessment
    # Do not delete unrelated files from the screenshots folder
    image_paths = []

    try:
        for uploaded_file in uploaded_files:
            extension = os.path.splitext(uploaded_file.name)[1].lower()

            if extension not in ALLOWED_IMAGE_TYPES:
                st.error(
                    f"Unsupported screenshot format: {extension or 'unknown'}. "
                    "Please upload PNG, JPG, JPEG or WEBP images."
                )
                return None, None

            # Use a generated temporary filename rather than the original filename to avoid collisions and unsafe path components
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix="upload_",
                suffix=extension,
                dir=SCREENSHOT_FOLDER,
                delete=False,
            ) as disk_file:
                disk_file.write(uploaded_file.getbuffer())
                image_paths.append(disk_file.name)

        input_key = data_manager.make_screenshot_key(
            user_input,
            image_paths,
        )

        # Reuse a previously saved assessment when the input matches
        if (
            data_manager.find_saved_record(
                input_key,
                st.session_state.records,
            )
            is not None
        ):
            return [], input_key

        # Stage 1: Extract the conversation from the screenshots.
        extraction = ai_manager.read_screenshots(image_paths)

        if not isinstance(extraction, dict) or not extraction.get("ok"):
            error = (
                extraction.get("error", "Unknown extraction error")
                if isinstance(extraction, dict)
                else "The screenshot reader returned an unexpected response."
            )

            st.error(f"Could not read screenshots: {error}")
            return None, None

        extracted_messages = extraction.get("data")

        if not isinstance(extracted_messages, list):
            st.error(
                "The screenshot reader returned an unexpected message format."
            )
            return None, None

        return extracted_messages, input_key

    except Exception as exc:
        st.error(f"Could not process the uploaded screenshots: {exc}")
        return None, None

    finally:
        # Delete only the temporary files created for this assessment
        for image_path in image_paths:
            try:
                if os.path.isfile(image_path):
                    os.remove(image_path)
            except OSError:
                # A cleanup failure should not hide the main assessment result
                pass

# ============================================================
# ASSESSMENT PIPELINE
# ============================================================

def run_assessment(source, user_input, messages, input_key):
    """
    Run AI analysis, deterministic risk scoring and AI feedback.

    Returns the assessment record, or None if the analysis fails.
    """

    saved_record = data_manager.find_saved_record(
        input_key,
        st.session_state.records,
    )

    # Reuse an existing AI analysis when the input matches
    if saved_record is not None:
        saved_ai_output = saved_record.get("ai_output")

        if not isinstance(saved_ai_output, dict):
            st.error(
                "The saved assessment has an invalid AI result. "
                "Please run the assessment again."
            )
            return None

        ai_result = {
            "ok": True,
            "data": saved_ai_output,
        }

        messages = saved_record.get("messages", messages)
        from_saved = True

    else:
        # Stage 2: Analyse the conversation using the AI Manager
        ai_result = ai_manager.analyze_chat(user_input, messages)
        from_saved = False

    if not isinstance(ai_result, dict) or not ai_result.get("ok"):
        error = (
            ai_result.get("error", "Unknown error")
            if isinstance(ai_result, dict)
            else "The AI Manager returned an unexpected response."
        )

        st.error(f"AI analysis failed: {error}")
        return None

    ai_output = ai_result.get("data")

    if not isinstance(ai_output, dict):
        st.error("The AI Manager returned an invalid analysis result.")
        return None

    # The Logic Manager calculates the score using Python rules
    # The AI provides findings; it does not determine the final score
    result = logic_manager.evaluate_risk(ai_output)

    # Stage 3: Generate explanatory feedback
    feedback = (
        saved_record.get("feedback")
        if saved_record is not None
        else None
    )

    if feedback is None:
        feedback_result = ai_manager.generate_feedback(
            user_input,
            ai_output,
            result,
        )

        if (
            isinstance(feedback_result, dict)
            and feedback_result.get("ok")
        ):
            feedback = feedback_result.get("data")
        else:
            error = (
                feedback_result.get("error", "Unknown error")
                if isinstance(feedback_result, dict)
                else "The feedback generator returned an unexpected response."
            )

            st.warning(
                "AI feedback is not available right now: "
                f"{error}"
            )

    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": source,
        "input_key": input_key,
        "input": user_input,
        "message_count": len(messages) if isinstance(messages, list) else 0,
        "messages": messages,
        "ai_output": ai_output,
        "result": result,
        "feedback": feedback,
        "from_saved": from_saved,
    }

    # Save only newly generated assessments
    if not from_saved:
        if data_manager.save_record(record):
            st.session_state.records.append(record)
        else:
            st.error(
                "Could not save this check to the records file. "
                "The current result is still available below."
            )

    return record

# ============================================================
# RESULT DISPLAY
# ============================================================

def show_result(record):
    """Display the risk score, feedback and supporting findings."""

    result = record["result"]

    score = result.get("score", 0)
    max_score = result.get("max_score", logic_manager.MAX_SCORE)
    risk_level = result.get("risk_level", "Medium Risk")

    st.markdown("### Final Risk Report")

    message = f"**Risk score: {score} / {max_score} ({risk_level})**"

    if risk_level == "High Risk":
        st.error(message)
    elif risk_level == "Medium Risk":
        st.warning(message)
    else:
        st.success(message)

    if isinstance(score, (int, float)) and isinstance(max_score, (int, float)):
        if max_score > 0:
            progress = max(0.0, min(float(score) / float(max_score), 1.0))
            st.progress(progress)

    if record.get("from_saved"):
        st.caption(
            "Same chat and details as before — reused the saved AI analysis."
        )

    # AI-generated feedback is displayed as text rather than interpreted as Markdown
    feedback = record.get("feedback")

    if isinstance(feedback, dict) and feedback.get("feedback"):
        st.markdown("#### What this means")
        st.write(feedback["feedback"])

        next_steps = feedback.get("next_steps", [])

        if isinstance(next_steps, list) and next_steps:
            st.markdown("#### What to do next")

            for step in next_steps:
                st.write(f"• {step}")

    else:
        advice = FALLBACK_ADVICE.get(
            risk_level,
            "Proceed carefully and verify the transaction details before paying.",
        )

        st.info(f"**Recommended Action:** {advice}")

    # Risk factors from the deterministic Logic Manager
    risk_factors = result.get("risk_factors", [])

    if isinstance(risk_factors, list) and risk_factors:
        st.markdown("#### Warning Signs Found")

        for factor in risk_factors:
            st.write(f"• {factor}")

    # Information that could not be established from the available evidence
    missing_information = result.get("missing_information", [])

    if isinstance(missing_information, list) and missing_information:
        st.markdown("#### Missing Information")

        for info in missing_information:
            st.write(f"• {info}")

    # Supporting evidence from the analysed conversation
    evidence = result.get("evidence", [])

    if isinstance(evidence, list) and evidence:
        st.markdown("#### Evidence From the Chat")

        for quote in evidence:
            st.write(f"• {quote}")

    # Show the conversation as plain text so that message content is not accidentally interpreted as Markdown
    messages = record.get("messages", [])

    if isinstance(messages, list) and messages:
        with st.expander(f"Messages the AI read ({len(messages)})"):
            for message in messages:
                if not isinstance(message, dict):
                    st.text(str(message))
                    continue

                sender = str(message.get("sender", "Unknown sender"))
                text = str(message.get("text", ""))
                date = message.get("date")

                if date:
                    st.text(f"{date} | {sender}: {text}")
                else:
                    st.text(f"{sender}: {text}")

    st.caption(
        "This assessment is intended to support your decision, "
        "not to prove that someone is a scammer."
    )

# ============================================================
# PAGE 1: CHECK A NEW DEAL
# ============================================================

def show_new_check():
    """Allow users to assess a deal using screenshots or a Telegram username."""

    source = st.radio(
        "How do you want to share the chat?",
        ["Screenshots", "Telegram username"],
        horizontal=True,
    )

    uploaded_files = []
    chat = ""

    if source == "Screenshots":
        chat = "Screenshots"

        uploaded_files = st.file_uploader(
            "Drag and drop chat screenshots here",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
        )

    else:
        # Telegram authentication is handled inline in this mode
        render_inline_telegram_login()

        # Only show the username field once authentication is available
        if st.session_state.get("tg_authenticated"):
            chat = st.text_input(
                "Seller's Telegram @username or link:",
                placeholder="@seller_admin",
            ).strip()

    # The AI identifies transaction details from the conversation
    user_input = {
        "chat": chat,
        "item": "",
        "price": 0.0,
        "details": "",
    }

    st.markdown("---")

    if not st.button("Assess Deal Risk", use_container_width=True):
        return

    # Validate the selected input mode before starting the pipeline
    if (
        source == "Telegram username"
        and not st.session_state.get("tg_authenticated")
    ):
        st.error("Please complete Telegram login above first.")

    elif source == "Telegram username" and not user_input["chat"]:
        st.error("Please enter the seller's Telegram @username or link.")

    elif source == "Screenshots" and not uploaded_files:
        st.error("Please upload at least one screenshot.")

    else:
        with st.spinner("Analysing the chat..."):
            messages, input_key = get_messages(
                source,
                user_input,
                uploaded_files,
            )

            record = None

            if messages is not None:
                record = run_assessment(
                    source,
                    user_input,
                    messages,
                    input_key,
                )

        if record is not None:
            show_result(record)

# ============================================================
# PAGE 2: VIEW PAST CHECKS
# ============================================================

def show_past_checks():
    """Display saved assessments, newest first, with a risk-level filter."""

    choice = st.selectbox(
        "Show which checks?",
        ["All", "High Risk", "Medium Risk", "Low Risk"],
    )

    if choice == "All":
        records = st.session_state.records
    else:
        records = data_manager.filter_by_risk_level(
            st.session_state.records,
            choice,
        )

    if not records:
        st.info("No matching past checks.")
        return

    for record in reversed(records):
        if not isinstance(record, dict):
            continue

        deal = record.get("input", {})
        result = record.get("result", {})

        if not isinstance(deal, dict):
            deal = {}

        if not isinstance(result, dict):
            result = {}

        score = result.get("score")

        if score is not None:
            score_text = (
                f"{score}/"
                f"{result.get('max_score', logic_manager.MAX_SCORE)}"
            )
        else:
            score_text = "no score"

        ai_output = record.get("ai_output", {})

        if not isinstance(ai_output, dict):
            ai_output = {}

        what = (
            deal.get("item")
            or ai_output.get("transaction_summary", "")
        )

        chat_name = deal.get("chat", "Unknown chat")
        timestamp = record.get("time", "Unknown time")
        risk_level = result.get("risk_level", "Unknown risk level")

        title = (
            f"{timestamp} | {chat_name} | {what[:60]} | "
            f"{risk_level} ({score_text})"
        )

        with st.expander(title):
            st.write(f"**Seller / chat:** {chat_name}")

            feedback = record.get("feedback")

            if isinstance(feedback, dict) and feedback.get("feedback"):
                st.write(feedback["feedback"])

            for factor in result.get("risk_factors", []):
                st.write(f"• {factor}")

# ============================================================
# MAIN PAGE
# ============================================================

st.title("Telegram Risk Assessor")

st.markdown(
    "Protect your online marketplace transactions with "
    "AI-assisted analysis of marketplace conversations."
)

st.markdown("---")

page = st.radio(
    "What would you like to do?",
    ["Check a new deal", "View past checks"],
    horizontal=True,
)

st.markdown("---")

if page == "Check a new deal":
    show_new_check()
else:
    show_past_checks()
    