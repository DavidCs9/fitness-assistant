import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

from shared.config import Config
from shared.dynamo import (
    save_meal, save_body_metrics, save_exercise,
    get_daily_summary, compute_and_save_daily_summary,
)
from shared.llm import extract_intent
from shared.models import MealLog, BodyMetrics, ExerciseLog, IntentType
from shared.whatsapp import parse_incoming_message, send_message, is_authorized

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: dict, context) -> dict:
    method = event.get("httpMethod", "")

    if method == "GET":
        return _verify_webhook(event)

    if method == "POST":
        return _handle_message(event)

    return {"statusCode": 405, "body": "Method Not Allowed"}


def _verify_webhook(event: dict) -> dict:
    params = event.get("queryStringParameters") or {}
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == Config.WHATSAPP_VERIFY_TOKEN:
        return {"statusCode": 200, "body": challenge}
    return {"statusCode": 403, "body": "Forbidden"}


def _handle_message(event: dict) -> dict:
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": "Bad Request"}

    phone, text = parse_incoming_message(body)

    # WhatsApp expects a 200 quickly; ignore non-text messages silently
    if phone is None or text is None:
        return {"statusCode": 200, "body": "OK"}

    if not is_authorized(phone):
        logger.warning("Unauthorized message from %s", phone)
        return {"statusCode": 200, "body": "OK"}

    try:
        _process_message(phone, text)
    except Exception:
        logger.exception("Error processing message from %s", phone)
        send_message(phone, "Hubo un error procesando tu mensaje. Intenta de nuevo.")

    return {"statusCode": 200, "body": "OK"}


def _process_message(phone: str, text: str) -> None:
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    extracted = extract_intent(text)
    intent = extracted.get("intent", IntentType.UNKNOWN)
    feedback = extracted.get("immediate_feedback", "")

    if intent == IntentType.MEAL_LOG:
        meal = MealLog(
            user_id=phone,
            timestamp=timestamp,
            meal_description=extracted.get("meal_description", text),
            estimated_calories=extracted.get("estimated_calories", 0),
            estimated_protein=extracted.get("estimated_protein", 0),
            estimated_fiber=extracted.get("estimated_fiber", 0),
            satiety_score=extracted.get("satiety_score", 3),
        )
        save_meal(meal)
        reply = feedback or _format_quick_summary(phone, today)

    elif intent == IntentType.BODY_METRICS:
        metrics = BodyMetrics(
            user_id=phone,
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
            user_id=phone,
            timestamp=timestamp,
            exercise_description=extracted.get("exercise_description", text),
            estimated_calories_burned=extracted.get("estimated_calories_burned", 0),
            steps=extracted.get("steps", 0),
        )
        save_exercise(exercise)
        reply = feedback or "Ejercicio registrado."

    elif intent == IntentType.QUERY_SUMMARY:
        summary = get_daily_summary(phone, today)
        if summary:
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

    send_message(phone, reply)


def _format_quick_summary(user_id: str, date: str) -> str:
    summary = compute_and_save_daily_summary(user_id, date)
    return (
        f"Registrado. Hoy: {summary.total_calories} cal | {summary.total_protein}g prot | "
        f"{summary.total_fiber}g fibra"
    )
