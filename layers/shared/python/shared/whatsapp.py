import json
import urllib.request
import urllib.parse
from typing import Optional

from shared.config import Config


def parse_incoming_message(body: dict) -> tuple[Optional[str], Optional[str]]:
    """
    Parse a WhatsApp Cloud API webhook payload.
    Returns (phone_number, message_text) or (None, None) if not a text message.
    """
    try:
        entry = body["entry"][0]
        change = entry["changes"][0]
        value = change["value"]
        message = value["messages"][0]
        if message.get("type") != "text":
            return None, None
        phone = message["from"]
        text = message["text"]["body"]
        return phone, text
    except (KeyError, IndexError):
        return None, None


def send_message(to: str, text: str) -> None:
    """Send a WhatsApp text message via the Cloud API."""
    url = (
        f"https://graph.facebook.com/{Config.WHATSAPP_API_VERSION}"
        f"/{Config.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {Config.WHATSAPP_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        resp.read()


def is_authorized(phone_number: str) -> bool:
    return phone_number in Config.ALLOWED_PHONE_NUMBERS
