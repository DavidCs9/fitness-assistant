import json
import urllib.request
from typing import Optional

from shared.config import Config

TELEGRAM_API = "https://api.telegram.org"


def parse_incoming_message(body: dict) -> tuple[Optional[str], Optional[str]]:
    message = body.get("message") or body.get("edited_message")
    if not message:
        return None, None
    chat_id = message.get("chat", {}).get("id")
    if chat_id is None:
        return None, None
    return str(chat_id), message.get("text")


def extract_voice_bytes(body: dict) -> Optional[bytes]:
    message = body.get("message") or body.get("edited_message")
    if not message:
        return None
    voice = message.get("voice") or message.get("audio")
    if not voice:
        return None
    file_id = voice.get("file_id")
    if not file_id:
        return None

    token = Config.get_telegram_bot_token()
    get_file_url = f"{TELEGRAM_API}/bot{token}/getFile?file_id={file_id}"
    with urllib.request.urlopen(get_file_url) as resp:
        file_info = json.loads(resp.read())
    file_path = file_info["result"]["file_path"]

    download_url = f"{TELEGRAM_API}/file/bot{token}/{file_path}"
    with urllib.request.urlopen(download_url) as resp:
        return resp.read()


def send_message(chat_id: str, text: str) -> None:
    """Send a Telegram text message via the Bot API."""
    url = f"{TELEGRAM_API}/bot{Config.get_telegram_bot_token()}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        resp.read()


def is_authorized(chat_id: str) -> bool:
    return chat_id in Config.get_allowed_chat_ids()


def verify_telegram_secret(event: dict) -> bool:
    headers = event.get("headers") or {}
    sent = (
        headers.get("x-telegram-bot-api-secret-token")
        or headers.get("X-Telegram-Bot-Api-Secret-Token")
    )
    return sent == Config.get_telegram_webhook_secret()
