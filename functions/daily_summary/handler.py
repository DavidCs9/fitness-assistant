import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from shared.config import Config
from shared.dynamo import compute_and_save_daily_summary, get_meals_for_date, get_profile
from shared.llm import generate_daily_summary_message
from shared.telegram import send_message

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: dict, context) -> dict:
    for chat_id in Config.get_allowed_chat_ids():
        try:
            _send_daily_summary(chat_id)
        except Exception:
            logger.exception("Failed to send daily summary to %s", chat_id)

    return {"statusCode": 200}


def _send_daily_summary(chat_id: str) -> None:
    profile = get_profile(chat_id)
    today = datetime.now(ZoneInfo(profile.timezone if profile else "UTC")).strftime("%Y-%m-%d")

    summary = compute_and_save_daily_summary(chat_id, today)

    if summary.meal_count == 0:
        logger.info("No meals for %s on %s, skipping summary", chat_id, today)
        return

    meals = get_meals_for_date(chat_id, today)
    message = generate_daily_summary_message(summary, meals, profile=profile)
    send_message(chat_id, message)
    logger.info("Sent daily summary to %s for %s", chat_id, today)
