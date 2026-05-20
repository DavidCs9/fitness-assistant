import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

from shared.dynamo import (
    save_meal, save_body_metrics, save_exercise,
    get_daily_summary, compute_and_save_daily_summary,
)
from shared.llm import extract_intent
from shared.models import MealLog, BodyMetrics, ExerciseLog, IntentType
from shared.telegram import (
    parse_incoming_message, send_message, is_authorized, verify_telegram_secret,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: dict, context) -> dict:
    if event.get("httpMethod", "") != "POST":
        return {"statusCode": 405, "body": "Method Not Allowed"}

    if not verify_telegram_secret(event):
        logger.warning("Webhook secret mismatch; rejecting request")
        return {"statusCode": 403, "body": "Forbidden"}

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": "Bad Request"}

    chat_id, text = parse_incoming_message(body)

    if chat_id is None or text is None:
        return {"statusCode": 200, "body": "OK"}

    if not is_authorized(chat_id):
        logger.warning("Unauthorized message from %s", chat_id)
        return {"statusCode": 200, "body": "OK"}

    try:
        _process_message(chat_id, text)
    except Exception:
        logger.exception("Error processing message from %s", chat_id)
        send_message(chat_id, "Hubo un error procesando tu mensaje. Intenta de nuevo.")

    return {"statusCode": 200, "body": "OK"}


def _process_message(chat_id: str, text: str) -> None:
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    extracted = extract_intent(text)
    intent = extracted.get("intent", IntentType.UNKNOWN)
    feedback = extracted.get("immediate_feedback", "")

    if intent == IntentType.MEAL_LOG:
        meal = MealLog(
            user_id=chat_id,
            timestamp=timestamp,
            meal_description=extracted.get("meal_description", text),
            estimated_calories=extracted.get("estimated_calories", 0),
            estimated_protein=extracted.get("estimated_protein", 0),
            estimated_fiber=extracted.get("estimated_fiber", 0),
            satiety_score=extracted.get("satiety_score", 3),
        )
        save_meal(meal)
        compute_and_save_daily_summary(chat_id, today)
        reply = feedback or _format_quick_summary(chat_id, today)

    elif intent == IntentType.BODY_METRICS:
        metrics = BodyMetrics(
            user_id=chat_id,
            date=today,
            weight_kg=Decimal(str(extracted["weight_kg"])) if extracted.get("weight_kg") else None,
            waist_inches=Decimal(str(extracted["waist_inches"])) if extracted.get("waist_inches") else None,
            neck_inches=Decimal(str(extracted["neck_inches"])) if extracted.get("neck_inches") else None,
            arms_inches=Decimal(str(extracted["arms_inches"])) if extracted.get("arms_inches") else None,
        )
        save_body_metrics(metrics)
        reply = feedback or "Métricas registradas."

    elif intent == IntentType.EXERCISE_LOG:
        exercise = ExerciseLog(
            user_id=chat_id,
            timestamp=timestamp,
            exercise_description=extracted.get("exercise_description", text),
            estimated_calories_burned=extracted.get("estimated_calories_burned", 0),
            steps=extracted.get("steps", 0),
        )
        save_exercise(exercise)
        compute_and_save_daily_summary(chat_id, today)
        reply = feedback or "Ejercicio registrado."

    elif intent == IntentType.QUERY_SUMMARY:
        # Fall back to on-demand computation if no materialized summary exists yet.
        summary = get_daily_summary(chat_id, today) or compute_and_save_daily_summary(chat_id, today)
        if summary.meal_count > 0 or summary.total_steps > 0 or summary.total_calories_burned > 0:
            reply = (
                f"Hoy: {summary.total_calories} cal | {summary.total_protein}g prot | "
                f"{summary.total_fiber}g fibra | {summary.total_steps} pasos\n"
                f"Riesgo hambre: {summary.hunger_risk()}"
            )
        else:
            reply = "Aún no tienes registros para hoy."

    elif intent == IntentType.QUERY_TREND:
        reply = "Recibirás tu resumen semanal el domingo. Sigue registrando!"

    else:
        reply = "No entendí tu mensaje. Puedes registrar comidas, ejercicio o métricas corporales."

    send_message(chat_id, reply)


def _format_quick_summary(user_id: str, date: str) -> str:
    summary = compute_and_save_daily_summary(user_id, date)
    return (
        f"Registrado. Hoy: {summary.total_calories} cal | {summary.total_protein}g prot | "
        f"{summary.total_fiber}g fibra"
    )
