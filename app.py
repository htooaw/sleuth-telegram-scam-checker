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