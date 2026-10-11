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