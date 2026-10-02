# ai_manager.py
# Talks to Gemini in two stages:
#   stage 1 - read chat screenshots into messages (screenshot mode only)
#   stage 2 - analyze the chat for scam warning signs
# Every answer is checked as JSON. Never crashes: always returns a result dict.

import json
import logging
import os
import time

# Import the core genai client library from the Google GenAI SDK
from google import genai
# Import types from the Google GenAI SDK for configuration and multimodal content parts
from google.genai import types

MODEL = "gemini-3.5-flash-lite"
MAX_ATTEMPTS = 3
WAIT_SECONDS = 2

# Define a dictionary of every field the AI must return, and its expected type
EXPECTED_FIELDS = {
    "transaction_summary": str,
    "advance_fee_detected": bool,
    "payment_plausibility": str,
    "payment_diversion_detected": bool,
    "social_engineering_tactics": list,
    "inconsistencies": list,
    "missing_information": list,
    "other_risk_indicators": list,
    "evidence": list,
}
PLAUSIBILITY_VALUES = ["High", "Medium", "Low"]