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

# --- IMPORTANT: MUST MATCH io_manager.py ---
SESSION_NAME = "anon"  
API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")

# Initialize records in session state
if "records" not in st.session_state:
    st.session_state.records = data_manager.load_records()

os.makedirs("data/screenshots", exist_ok=True)

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