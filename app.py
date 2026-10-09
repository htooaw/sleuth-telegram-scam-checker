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


# ==========================================
# SIDEBAR: TELEGRAM AUTHENTICATION UI
# ==========================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/telegram-app--v1.png", width=60)
    st.title("Telegram Auth")
    st.markdown("---")

    if "tg_authenticated" not in st.session_state:
        try:
            st.session_state.tg_authenticated = run_async(check_auth())
        except Exception:
            st.session_state.tg_authenticated = False

    if st.session_state.tg_authenticated:
        st.success("Logged in securely")
    else:
        st.warning("Not authenticated")
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


# ==========================================
# MAIN PAGE: DASHBOARD INTERFACE
# ==========================================
st.title("Telegram Risk Assessor")
st.markdown("Protect your online marketplace transactions with real-time AI behavioral analysis.")
st.markdown("---")

# UI: Mode selector layout
source = st.radio("Choose Verification Source:", ["Screenshots", "Telegram Link"], horizontal=True)

user_input = {}

# UI: Adding Columns for better layout
col1, col2 = st.columns([1, 1])

with col1:
    if source == "Telegram Link":
        user_input["chat"] = st.text_input("Telegram Chat (@username or link):", placeholder="@seller_admin")
    else:
        user_input["chat"] = st.text_input("Seller Handle (Optional):", value="")

with col2:
    user_input["item"] = st.text_input("Item Name:", placeholder="e.g., Vintage OOTD Set")

col3, col4 = st.columns([1, 1])
with col3:
    user_input["price"] = float(st.number_input("Agreed Price (SGD):", min_value=0.0, step=1.0, value=0.0))
with col4:
    user_input["details"] = st.text_input("Extra Details (Optional):", value="", placeholder="e.g., meetup vs delivery")

uploaded_files = []
if source == "Screenshots":
    st.markdown("")
    uploaded_files = st.file_uploader("Drag and drop chat screenshots here", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

st.markdown("---")

# --- EXECUTION LOGIC ---
if st.button("Assess Deal Risk", use_container_width=True):
    if source == "Telegram Link" and not st.session_state.tg_authenticated:
        st.error("⚠️ You must authenticate via the sidebar login first!")
    elif not user_input["item"]:
        st.error("⚠️ Please specify the item name before running the assessment.")
    elif source == "Telegram Link" and not user_input.get("chat"):
        st.error("⚠️ Please enter a valid Telegram chat identifier.")
    elif source == "Screenshots" and not uploaded_files:
        st.error("⚠️ Please upload at least one screenshot to analyze.")
    else:
        with st.spinner("Analyzing transaction behaviour and security flags..."):
            messages = None
            input_key = None
            
            # 1. Gather Data based on source
            if source == "Telegram Link":
                messages, error = io_manager.fetch_chat_messages(user_input["chat"])
                if error:
                    st.error(f"Failed to read chat: {error}")
                    messages = None
                else:
                    input_key = data_manager.make_input_key(user_input, messages)
                    
            elif source == "Screenshots":
                for old_file in os.listdir("data/screenshots"):
                    os.remove(os.path.join("data/screenshots", old_file))
                
                image_paths = []
                for f in uploaded_files:
                    path = os.path.join("data/screenshots", f.name)
                    with open(path, "wb") as disk_file:
                        disk_file.write(f.getbuffer())
                    image_paths.append(path)
                
                input_key = data_manager.make_screenshot_key(user_input, image_paths)
                
                saved_record = data_manager.find_saved_record(input_key, st.session_state.records)
                if saved_record is not None:
                    messages = [] 
                else:
                    extraction = ai_manager.read_screenshots(image_paths)
                    if not extraction["ok"]:
                        st.error(f"Could not read screenshots: {extraction['error']}")
                    else:
                        messages = extraction["data"]

            # 2. Run Assessment 
            if messages is not None:
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
                else:
                    result = logic_manager.evaluate_risk(ai_result)
                    
                    record = {
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "source": source.lower(),
                        "input_key": input_key,
                        "input": user_input,
                        "message_count": len(messages),
                        "messages": messages,
                        "ai_output": ai_result.get("data"),
                        "result": result,
                        "from_saved": from_saved,
                    }
                    
                    if not from_saved:
                        if data_manager.save_record(record):
                            st.session_state.records.append(record)
                    
                    # 3. Display Polished Results Dashboard
                    st.markdown("### Final Risk Report")
                    
                    risk_level = result['risk_level']
                    if risk_level == "High Risk":
                        st.error(f"🚨 **Risk Level: {risk_level}**")
                    elif risk_level == "Medium Risk":
                        st.warning(f"⚠️ **Risk Level: {risk_level}**")
                    else:
                        st.success(f"✅ **Risk Level: {risk_level}**")
                    
                    st.info(f"**Recommended Action:** {result['action']}")
                    st.markdown(f"**Analysis Summary:** {result['reason']}")
                    
                    if result.get("risk_factors"):
                        st.markdown("#### Warning Signs Found:")
                        for factor in result["risk_factors"]:
                            st.markdown(f"- {factor}")
                            
                    if result.get("missing_information"):
                        st.markdown("#### Missing Information:")
                        for info in result["missing_information"]:
                            st.markdown(f"- {info}")