import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from shared.config import Config
from shared.dynamo import get_daily_summaries_range, get_body_metrics_range, get_profile
from shared.llm import generate_weekly_trend_message
from shared.telegram import send_message

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: dict, context) -> dict:
    for chat_id in Config.ALLOWED_CHAT_IDS:
        try:
            _send_weekly_trend(chat_id)
        except Exception:
            logger.exception("Failed to send weekly trend to %s", chat_id)

    return {"statusCode": 200}


def _send_weekly_trend(chat_id: str) -> None:
    profile = get_profile(chat_id)
    now = datetime.now(ZoneInfo(profile.timezone if profile else "UTC"))
    end_date = now.strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=6)).strftime("%Y-%m-%d")

    days = get_daily_summaries_range(chat_id, start_date, end_date)
    body_metrics = get_body_metrics_range(chat_id, start_date, end_date)

    if not days:
        logger.info("No data for %s in range %s-%s, skipping", chat_id, start_date, end_date)
        return

    message = generate_weekly_trend_message(days, body_metrics, profile=profile)
    send_message(chat_id, message)
    logger.info("Sent weekly trend to %s (%s to %s)", chat_id, start_date, end_date)
