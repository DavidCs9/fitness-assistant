import logging
from datetime import datetime, timezone

from shared.config import Config
from shared.dynamo import compute_and_save_daily_summary, get_meals_for_date
from shared.llm import generate_daily_summary_message
from shared.telegram import send_message

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: dict, context) -> dict:
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    for chat_id in Config.ALLOWED_CHAT_IDS:
        try:
            _send_daily_summary(chat_id, today)
        except Exception:
            logger.exception("Failed to send daily summary to %s", chat_id)

    return {"statusCode": 200}


def _send_daily_summary(chat_id: str, date: str) -> None:
    summary = compute_and_save_daily_summary(chat_id, date)

    if summary.meal_count == 0:
        logger.info("No meals for %s on %s, skipping summary", chat_id, date)
        return

    meals = get_meals_for_date(chat_id, date)
    message = generate_daily_summary_message(summary, meals)
    send_message(chat_id, message)
    logger.info("Sent daily summary to %s for %s", chat_id, date)
