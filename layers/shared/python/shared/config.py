import os


class Config:
    TABLE_NAME = os.environ.get("TABLE_NAME", "FitnessAssistant-dev")
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
    WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
    ALLOWED_PHONE_NUMBERS = set(
        n.strip() for n in os.environ.get("ALLOWED_PHONE_NUMBERS", "").split(",") if n.strip()
    )
    WHATSAPP_API_VERSION = "v19.0"
    CLAUDE_MODEL = "claude-haiku-4-5"
