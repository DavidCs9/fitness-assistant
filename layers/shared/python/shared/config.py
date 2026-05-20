import os


class Config:
    TABLE_NAME = os.environ.get("TABLE_NAME", "FitnessAssistant-dev")
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    ALLOWED_CHAT_IDS = set(
        n.strip() for n in os.environ.get("ALLOWED_CHAT_IDS", "").split(",") if n.strip()
    )
    CLAUDE_MODEL = "claude-haiku-4-5"
