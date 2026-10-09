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

# Define a function to construct the prompt and format the chat history for stage 2 scam analysis
def build_prompt(user_input, messages):
    """Create the instructions and chat text we send to Gemini."""
    chat_lines = []
    for message in messages:
        chat_lines.append("[" + message["date"] + "] " + message["sender"] + ": " + message["text"])
    chat_text = "\n".join(chat_lines)

    details = user_input["details"] if user_input["details"] else "None"

    return f"""You are a fraud analyst checking a Telegram marketplace deal for a BUYER.
Messages from the buyer are labelled "You". Judge only what is in the chat.

Deal details from the buyer:
- Item: {user_input['item']}
- Agreed price: SGD {user_input['price']:.2f}
- Extra details: {details}

Telegram chat ({len(messages)} messages, oldest first):
{chat_text}

Reply with ONLY a JSON object with exactly these fields:
{{
  "transaction_summary": "one sentence describing the deal",
  "advance_fee_detected": true or false (seller asks for a deposit, fee or full payment before delivery),
  "payment_plausibility": "High", "Medium" or "Low" (how safe and normal the payment method is),
  "payment_diversion_detected": true or false (moves to another app, or pays a different person/account),
  "social_engineering_tactics": ["list of pressure tactics, e.g. urgency, scarcity"],
  "inconsistencies": ["list of contradictions in the chat or with the deal details"],
  "missing_information": ["list of important deal details that are missing"],
  "other_risk_indicators": ["any other warning signs"],
  "evidence": ["short quotes from the chat that support your findings"]
}}
Use empty lists when nothing is found."""

def validate_ai_output(data):
    """Check the AI answer has every field with the right type. Returns a list of problems."""
    if not isinstance(data, dict):
        return ["AI answer is not a JSON object"]

    problems = []
    for field, expected_type in EXPECTED_FIELDS.items():
        if field not in data:
            problems.append("missing field: " + field)
        elif not isinstance(data[field], expected_type):
            problems.append("wrong type for field: " + field)

    if data.get("payment_plausibility") not in PLAUSIBILITY_VALUES:
        problems.append("payment_plausibility must be High, Medium or Low")

    return problems

def parse_ai_text(text, validate_function=validate_ai_output):
    """Turn the AI's text into a dict and check it. Returns (data, problems)."""
    if not text:
        return None, ["AI returned an empty answer"]

    # Some models wrap JSON in ```json ... ``` - remove
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, ["AI answer is not valid JSON"]

    problems = validate_function(data)
    if problems:
        return None, problems
    return data, []

SCREENSHOT_PROMPT = """These images are screenshots of a Telegram conversation OR a marketplace listing.
If it is a chat conversation, the person who took the screenshots is the BUYER. Their messages are usually on the RIGHT side. The other person's messages are usually on the LEFT.

If it is a chat, copy out every chat message in order.
If the image is just a product listing, advertisement, or channel broadcast with no chat bubbles, treat the entire text of the post as a single message sent by the "Seller".

Reply with ONLY a JSON object like this:
{
  "messages": [
    {"sender": "You", "date": "time shown next to the message, or empty string", "text": "exact message text"},
    {"sender": "Seller", "date": "", "text": "..."}
  ]
}
Use "You" for the buyer. For the other person use their name if it is shown, otherwise "Seller".
Do not add, fix or summarise any text. If there is absolutely no text at all in the images, return {"messages": []}."""

# Define a function to validate the structured output data extracted during stage 1 screenshot processing
def validate_extracted_messages(data):
    """Check the stage 1 answer: a list of messages with sender, date and text."""
    if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
        return ["AI answer must be an object with a 'messages' list"]

    problems = []
    for message in data["messages"]:
        if not isinstance(message, dict):
            problems.append("each message must be an object")
            continue
        for field in ["sender", "date", "text"]:
            if not isinstance(message.get(field), str):
                problems.append("message is missing text field: " + field)
    return problems
