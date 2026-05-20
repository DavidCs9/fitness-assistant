import logging
from datetime import datetime, timezone, timedelta

from shared.config import Config
from shared.dynamo import compute_and_save_daily_summary, get_meals_for_date
from shared.llm import generate_daily_summary_message
from shared.whatsapp import send_message

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: dict, context) -> dict:
    # Run for yesterday (this job fires at 11 PM, summarize today so far)
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    for phone in Config.ALLOWED_PHONE_NUMBERS:
        try:
            _send_daily_summary(phone, today)
        except Exception:
            logger.exception("Failed to send daily summary to %s", phone)

    return {"statusCode": 200}


def _send_daily_summary(phone: str, date: str) -> None:
    summary = compute_and_save_daily_summary(phone, date)

    if summary.meal_count == 0:
        logger.info("No meals for %s on %s, skipping summary", phone, date)
        return

    meals = get_meals_for_date(phone, date)
    message = generate_daily_summary_message(summary, meals)
    send_message(phone, message)
    logger.info("Sent daily summary to %s for %s", phone, date)
