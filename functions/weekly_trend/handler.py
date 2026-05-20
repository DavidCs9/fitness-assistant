import logging
from datetime import datetime, timezone, timedelta

from shared.config import Config
from shared.dynamo import get_daily_summaries_range, get_body_metrics_range
from shared.llm import generate_weekly_trend_message
from shared.whatsapp import send_message

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: dict, context) -> dict:
    now = datetime.now(timezone.utc)
    end_date = now.strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=6)).strftime("%Y-%m-%d")

    for phone in Config.ALLOWED_PHONE_NUMBERS:
        try:
            _send_weekly_trend(phone, start_date, end_date)
        except Exception:
            logger.exception("Failed to send weekly trend to %s", phone)

    return {"statusCode": 200}


def _send_weekly_trend(phone: str, start_date: str, end_date: str) -> None:
    days = get_daily_summaries_range(phone, start_date, end_date)
    body_metrics = get_body_metrics_range(phone, start_date, end_date)

    if not days:
        logger.info("No data for %s in range %s-%s, skipping", phone, start_date, end_date)
        return

    message = generate_weekly_trend_message(days, body_metrics)
    send_message(phone, message)
    logger.info("Sent weekly trend to %s (%s to %s)", phone, start_date, end_date)
