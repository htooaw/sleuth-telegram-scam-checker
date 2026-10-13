# ai_manager.py
# Talks to Gemini in two stages:
#   stage 1 - read chat screenshots into messages (screenshot mode only)
#   stage 2 - analyze the chat for scam warning signs
# Every answer is checked as JSON. Never crashes: always returns a result dict.

import json
import logging
import os
import time
from collections.abc import Callable

# Import the core genai client library from the Google GenAI SDK
from google import genai
# Import types from the Google GenAI SDK for configuration and multimodal content parts
from google.genai import types

# Tried in order; the next model is used only if the previous one keeps failing
MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
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

def describe_deal(user_input: dict) -> str:
    """Deal details for the prompts. The frontend only asks for the chat, so these may be empty."""
    if not user_input.get("item"):
        return "The buyer did not type any deal details. Work out the item, price and payment terms from the chat."
    details = user_input["details"] if user_input.get("details") else "None"
    return f"""- Item: {user_input['item']}
- Agreed price: SGD {user_input['price']:.2f}
- Extra details: {details}"""

# Define a function to construct the prompt and format the chat history for stage 2 scam analysis
def build_prompt(user_input: dict, messages: list[dict]) -> str:
    """Create the instructions and chat text we send to Gemini."""
    chat_lines = []
    for message in messages:
        chat_lines.append("[" + message["date"] + "] " + message["sender"] + ": " + message["text"])
    chat_text = "\n".join(chat_lines)

    return f"""You are a fraud analyst checking a Telegram marketplace deal for a BUYER.
Messages from the buyer are labelled "You". Judge only what is in the chat.

Deal details from the buyer:
{describe_deal(user_input)}

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

# Define a function to validate that the parsed AI response data matches the required schema and types
def validate_ai_output(data: object) -> list[str]:
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

# Define a function to clean up raw AI text response, parse it into JSON, and run validation checks
def parse_ai_text(text: str, validate_function: Callable[[object], list[str]] = validate_ai_output) -> tuple[dict | None, list[str]]:
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

# Define a function to send a content request directly to the Gemini API using the Google GenAI client
def call_gemini(contents: str | list, api_key: str, model: str) -> str:
    """Send one request to Gemini and return its text answer.
    contents is the prompt text, or a list of images plus the prompt."""
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0,  # as consistent as possible
            response_mime_type="application/json",
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    return response.text

# Define a function to handle calling Gemini with automatic retries, error handling, and validation loops
def ask_gemini(contents: str | list, validate_function: Callable[[object], list[str]]) -> dict:
    """Call Gemini, check the JSON answer, and retry if something goes wrong.
    Returns {"ok": True, "data": {...}} or {"ok": False, "error": "..."}."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logging.error("GEMINI_API_KEY is missing")
        return {"ok": False, "error": "GEMINI_API_KEY is missing from the .env file"}

    last_error = ""
    for model in MODELS:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                text = call_gemini(contents, api_key, model)
            except Exception as error:  # model unavailable, network problem, bad key, server busy...
                last_error = model + ": could not reach Gemini (" + str(error)[:150] + ")"
            else:
                data, problems = parse_ai_text(text, validate_function)
                if data is not None:
                    return {"ok": True, "data": data}
                last_error = model + ": invalid AI answer (" + "; ".join(problems) + ")"

            logging.warning("%s attempt %d of %d failed: %s", model, attempt, MAX_ATTEMPTS, last_error)
            if attempt < MAX_ATTEMPTS:
                time.sleep(WAIT_SECONDS)

        if model != MODELS[-1]:
            logging.warning("Switching from %s to the next model", model)

    logging.error("AI analysis gave up after trying all models")
    return {"ok": False, "error": last_error + " (all models failed)"}

# Define a high-level function for stage 2 to analyze chat content for fraud warning signs
def analyze_chat(user_input: dict, messages: list[dict]) -> dict:
    """AI stage 2: judge the chat for scam warning signs."""
    prompt = build_prompt(user_input, messages)
    return ask_gemini(prompt, validate_ai_output)


# ---------- AI stage 1: read chat screenshots ----------

# Define a mapping dictionary of supported image file extensions to their corresponding MIME types
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".heic": "image/heic",
}

# Define the specialized prompt instructions used in stage 1 to extract structured messages from screenshots
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
def validate_extracted_messages(data: object) -> list[str]:
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

# Define a function to load image files from disk, format them for Gemini, and extract chat messages (Stage 1)
def read_screenshots(image_paths: list[str]) -> dict:
    """AI stage 1: turn chat screenshots into a list of messages.
    Returns {"ok": True, "data": [messages]} or {"ok": False, "error": "..."}."""
    contents = []
    for path in image_paths:
        extension = os.path.splitext(path)[1].lower()
        try:
            with open(path, "rb") as file:
                image_bytes = file.read()
        except OSError:
            return {"ok": False, "error": "could not open " + path}
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type=IMAGE_TYPES[extension]))
    contents.append(SCREENSHOT_PROMPT)

    result = ask_gemini(contents, validate_extracted_messages)
    if not result["ok"]:
        return result

    messages = result["data"]["messages"]
    for message in messages:
        # Join text that was split over several lines in the chat bubble
        message["text"] = " ".join(message["text"].split())
    if not messages:
        return {"ok": False, "error": "no chat messages could be read from the screenshots"}
    return {"ok": True, "data": messages}

def build_feedback_prompt(user_input: dict, ai_output: dict, score_result: dict) -> str:
    """Create the instructions for Gemini to explain the score to the buyer."""
    return f"""You are helping a BUYER on a Telegram marketplace decide whether a deal is safe.
Our rule-based checker has already given this deal a risk score. Do NOT change the score.
Explain it in simple, friendly language and tell the buyer what to do next.

Deal:
{describe_deal(user_input)}

Risk score: {score_result['score']} out of {score_result['max_score']} ({score_result['risk_level']})
Warning signs found: {json.dumps(score_result['risk_factors'])}
Missing information: {json.dumps(score_result['missing_information'])}
Evidence from the chat: {json.dumps(score_result['evidence'])}
Summary of the deal: {ai_output.get('transaction_summary', '')}

Reply with ONLY a JSON object with exactly these fields:
{{
  "feedback": "2 to 4 sentences explaining why the deal got this score",
  "next_steps": ["2 to 4 short, practical things the buyer should do next"]
}}"""

def validate_feedback(data: object) -> list[str]:
    """Check the feedback answer has a feedback text and a list of next steps."""
    if not isinstance(data, dict):
        return ["AI answer is not a JSON object"]

    problems = []
    if not isinstance(data.get("feedback"), str) or not data.get("feedback").strip():
        problems.append("feedback must be a non-empty text")
    if not isinstance(data.get("next_steps"), list):
        problems.append("next_steps must be a list")
    else:
        for step in data["next_steps"]:
            if not isinstance(step, str):
                problems.append("each next step must be text")
    return problems

def generate_feedback(user_input: dict, ai_output: dict, score_result: dict) -> dict:
    """AI stage 3: write feedback that explains the score.
    Returns {"ok": True, "data": {"feedback": ..., "next_steps": [...]}} or {"ok": False, "error": "..."}."""
    prompt = build_feedback_prompt(user_input, ai_output, score_result)
    return ask_gemini(prompt, validate_feedback)

