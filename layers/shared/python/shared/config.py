import json
import os


def _load_secrets() -> dict:
    secrets_id = os.environ.get("SECRETS_ID")
    if not secrets_id:
        return {}
    import boto3
    client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "us-west-1"))
    return json.loads(client.get_secret_value(SecretId=secrets_id)["SecretString"])


_secrets: dict | None = None


def _get(key: str, fallback: str = "") -> str:
    global _secrets
    if _secrets is None:
        _secrets = _load_secrets()
    return _secrets.get(key) or os.environ.get(key, fallback)


class Config:
    TABLE_NAME = os.environ.get("TABLE_NAME", "FitnessAssistant-dev")
    CLAUDE_MODEL = "claude-haiku-4-5"

    @classmethod
    def get_anthropic_api_key(cls) -> str:
        return _get("ANTHROPIC_API_KEY")

    @classmethod
    def get_telegram_bot_token(cls) -> str:
        return _get("TELEGRAM_BOT_TOKEN")

    @classmethod
    def get_telegram_webhook_secret(cls) -> str:
        return _get("TELEGRAM_WEBHOOK_SECRET")

    @classmethod
    def get_allowed_chat_ids(cls) -> set:
        raw = _get("ALLOWED_CHAT_IDS")
        return set(n.strip() for n in raw.split(",") if n.strip())
