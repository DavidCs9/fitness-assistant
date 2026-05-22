import json
import logging
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from shared.dynamo import (
    save_meal, save_body_metrics, save_exercise,
    get_daily_summary, compute_and_save_daily_summary, get_profile,
    get_meals_for_date, get_exercises_for_date,
)
from shared.llm import extract_intent, transcribe_voice
from shared.models import MealLog, BodyMetrics, ExerciseLog, IntentType
from shared.telegram import (
    parse_incoming_message, extract_voice_bytes, send_message, is_authorized, verify_telegram_secret,
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

    if chat_id is None:
        return {"statusCode": 200, "body": "OK"}

    if text is None:
        voice_bytes = extract_voice_bytes(body)
        if voice_bytes is not None:
            try:
                text = transcribe_voice(voice_bytes)
            except Exception:
                logger.exception("Voice transcription failed for %s", chat_id)
                send_message(chat_id, "No pude transcribir tu nota de voz. Intenta de nuevo.")
                return {"statusCode": 200, "body": "OK"}

    if text is None:
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
    profile = get_profile(chat_id)
    now = datetime.now(ZoneInfo(profile.timezone if profile else "UTC"))
    today = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%S")

    today_progress = get_daily_summary(chat_id, today)

    logger.info(json.dumps({
        "event": "message_received",
        "chat_id": chat_id,
        "today": today,
        "today_progress": {
            "total_calories": today_progress.total_calories if today_progress else None,
            "total_protein": today_progress.total_protein if today_progress else None,
            "total_fiber": today_progress.total_fiber if today_progress else None,
            "meal_count": today_progress.meal_count if today_progress else None,
        },
    }))

    extracted = extract_intent(text, profile=profile, today_progress=today_progress)
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
        summary = get_daily_summary(chat_id, today) or compute_and_save_daily_summary(chat_id, today)
        if summary.meal_count > 0 or summary.total_steps > 0 or summary.total_calories_burned > 0:
            meals = get_meals_for_date(chat_id, today)
            exercises = get_exercises_for_date(chat_id, today)

            meal_lines = "\n".join(
                f"  • {m.meal_description} ({m.estimated_calories} cal, {m.estimated_protein}g prot)"
                for m in meals
            )
            exercise_lines = "\n".join(
                f"  • {e.exercise_description} ({e.estimated_calories_burned} cal quemadas)"
                for e in exercises
            )

            if profile:
                cal_left = profile.target_calories - summary.total_calories
                prot_left = profile.target_protein_g - summary.total_protein
                fiber_left = profile.target_fiber_g - summary.total_fiber
                totals = (
                    f"Hoy: {summary.total_calories}/{profile.target_calories} cal "
                    f"({'faltan' if cal_left > 0 else 'sobran'} {abs(cal_left)})\n"
                    f"Proteína: {summary.total_protein}/{profile.target_protein_g}g "
                    f"({'faltan' if prot_left > 0 else 'sobran'} {abs(prot_left)}g)\n"
                    f"Fibra: {summary.total_fiber}/{profile.target_fiber_g}g "
                    f"({'faltan' if fiber_left > 0 else 'sobran'} {abs(fiber_left)}g)\n"
                    f"Pasos: {summary.total_steps} | Quemadas ejercicio: {summary.total_calories_burned}\n"
                    f"Riesgo hambre: {summary.hunger_risk()}"
                )
            else:
                totals = (
                    f"Hoy: {summary.total_calories} cal | {summary.total_protein}g prot | "
                    f"{summary.total_fiber}g fibra | {summary.total_steps} pasos\n"
                    f"Riesgo hambre: {summary.hunger_risk()}"
                )

            reply = totals
            if meal_lines:
                reply += f"\n\nComidas:\n{meal_lines}"
            if exercise_lines:
                reply += f"\n\nEjercicios:\n{exercise_lines}"
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
