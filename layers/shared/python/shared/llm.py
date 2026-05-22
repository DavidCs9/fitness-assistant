import anthropic
import json
import logging
import urllib.request
import uuid
from typing import Optional

from shared.config import Config
from shared.models import DailySummary, BodyMetrics, Profile

logger = logging.getLogger(__name__)

_client = None

# Pricing per million tokens for claude-haiku-4-5 (update if Anthropic changes rates)
_PRICE_PER_M = {
    "input": 0.80,
    "output": 4.00,
    "cache_write": 1.00,
    "cache_read": 0.08,
}


def _log_usage(response: anthropic.types.Message, caller: str) -> None:
    u = response.usage
    cost = (
        getattr(u, "input_tokens", 0) * _PRICE_PER_M["input"]
        + getattr(u, "output_tokens", 0) * _PRICE_PER_M["output"]
        + getattr(u, "cache_creation_input_tokens", 0) * _PRICE_PER_M["cache_write"]
        + getattr(u, "cache_read_input_tokens", 0) * _PRICE_PER_M["cache_read"]
    ) / 1_000_000
    logger.info(
        json.dumps({
            "event": "llm_usage",
            "caller": caller,
            "model": response.model,
            "input_tokens": getattr(u, "input_tokens", 0),
            "output_tokens": getattr(u, "output_tokens", 0),
            "cache_creation_tokens": getattr(u, "cache_creation_input_tokens", 0),
            "cache_read_tokens": getattr(u, "cache_read_input_tokens", 0),
            "estimated_cost_usd": round(cost, 8),
        })
    )


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=Config.get_anthropic_api_key())
    return _client


def transcribe_voice(audio_bytes: bytes) -> str:
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="model"\r\n\r\nwhisper-1\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="language"\r\n\r\nes\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="voice.ogg"\r\n'
        f"Content-Type: audio/ogg\r\n\r\n"
    ).encode() + audio_bytes + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/transcriptions",
        data=body,
        headers={
            "Authorization": f"Bearer {Config.get_openai_api_key()}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        text = json.loads(resp.read())["text"]
    logger.info(json.dumps({"event": "voice_transcription", "transcript": text}))
    return text


SYSTEM_PROMPT = """Eres un asistente de fitness personal que ayuda a registrar comidas, ejercicio y métricas corporales.

El usuario te enviará mensajes en español describiendo lo que comió, hizo ejercicio, o sus métricas corporales.

Tu trabajo es extraer la información estructurada de esos mensajes y proporcionar retroalimentación útil y motivadora.

Para comidas, estima calorías, proteínas y fibra basándote en el contenido del mensaje.
Para ejercicio, estima calorías quemadas y pasos si aplica.
Para métricas corporales, extrae los valores numéricos mencionados.

La retroalimentación (immediate_feedback) debe ser:
- Breve (máximo 2 oraciones)
- En español
- Útil y específica (menciona los valores estimados)
- Cuando exista un perfil del usuario con metas (calorías, proteína), compara contra esas metas y menciona cuánto falta o por cuánto se pasó. No prediques, sé directo y útil.
- Motivadora pero honesta

Ejemplos:
- Sin perfil: "Buen desayuno. Estimé ~350 cal y 25g de proteína."
- Con perfil (meta 2000 cal, 200g prot): "Buen desayuno. ~350 cal y 25g prot — te quedan 1650 cal y 175g prot para hoy."
"""


def _profile_block(profile: Optional[Profile]) -> str:
    if profile is None:
        return ""
    return (
        f"\n\nPerfil del usuario (úsalo para personalizar retroalimentación):\n"
        f"- Edad: {profile.age}, Sexo: {profile.sex}, Altura: {profile.height_cm}cm\n"
        f"- Peso inicial: {profile.baseline_weight_kg}kg ({profile.baseline_date})\n"
        f"- Meta: {profile.goal}\n"
        f"- Metas diarias: {profile.target_calories} cal, "
        f"{profile.target_protein_g}g proteína, {profile.target_fat_g}g grasa, "
        f"{profile.target_carbs_g}g carbohidratos, {profile.target_fiber_g}g fibra\n"
        f"- TDEE estimado: {profile.tdee} cal/día"
    )


EXTRACTION_TOOL = {
    "name": "log_fitness_data",
    "description": "Extrae datos de fitness del mensaje del usuario y retorna datos estructurados",
    "input_schema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": ["meal_log", "body_metrics", "exercise_log", "query_summary", "query_trend", "unknown"],
                "description": "Tipo de dato que el usuario está registrando o consultando",
            },
            "meal_description": {
                "type": "string",
                "description": "Descripción normalizada de la comida",
            },
            "estimated_calories": {
                "type": "integer",
                "description": "Calorías estimadas de la comida",
            },
            "estimated_protein": {
                "type": "integer",
                "description": "Proteína estimada en gramos",
            },
            "estimated_fiber": {
                "type": "integer",
                "description": "Fibra estimada en gramos",
            },
            "satiety_score": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
                "description": "Nivel de saciedad estimado (1=muy poco, 5=muy satisfactorio)",
            },
            "weight_kg": {
                "type": "number",
                "description": "Peso en kilogramos",
            },
            "waist_inches": {
                "type": "number",
                "description": "Cintura en pulgadas",
            },
            "neck_inches": {
                "type": "number",
                "description": "Cuello en pulgadas",
            },
            "arms_inches": {
                "type": "number",
                "description": "Brazos en pulgadas",
            },
            "exercise_description": {
                "type": "string",
                "description": "Descripción normalizada del ejercicio",
            },
            "estimated_calories_burned": {
                "type": "integer",
                "description": "Calorías quemadas estimadas",
            },
            "steps": {
                "type": "integer",
                "description": "Pasos caminados o corridos",
            },
            "immediate_feedback": {
                "type": "string",
                "description": "Retroalimentación breve y útil para el usuario (en español, máximo 2 oraciones)",
            },
        },
        "required": ["intent"],
    },
}


def _progress_block(profile: Profile, today_progress: Optional[DailySummary]) -> str:
    if today_progress is None:
        return ""
    consumed_cal = today_progress.total_calories
    consumed_prot = today_progress.total_protein
    consumed_fiber = today_progress.total_fiber
    burned = today_progress.total_calories_burned
    remaining_cal = profile.target_calories - consumed_cal
    remaining_prot = profile.target_protein_g - consumed_prot
    remaining_fiber = profile.target_fiber_g - consumed_fiber
    return (
        f"\n\nProgreso de hoy hasta ahora (ANTES de registrar este mensaje):\n"
        f"- Consumido: {consumed_cal} cal, {consumed_prot}g proteína, {consumed_fiber}g fibra\n"
        f"- Quemado por ejercicio: {burned} cal\n"
        f"- Restante para meta: {remaining_cal} cal, {remaining_prot}g proteína, {remaining_fiber}g fibra\n"
        f"Usa estos valores exactos para calcular cuánto queda después de este registro. No hagas aritmética propia."
    )


def extract_intent(message: str, profile: Optional[Profile] = None, today_progress: Optional[DailySummary] = None) -> dict:
    system_blocks = [
        {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
    ]
    profile_text = _profile_block(profile)
    if profile_text:
        if profile is not None:
            profile_text += _progress_block(profile, today_progress)
        system_blocks.append({"type": "text", "text": profile_text})

    logger.info(json.dumps({
        "event": "extract_intent_input",
        "message": message,
        "today_progress": {
            "total_calories": today_progress.total_calories if today_progress else None,
            "total_protein": today_progress.total_protein if today_progress else None,
            "total_fiber": today_progress.total_fiber if today_progress else None,
            "total_calories_burned": today_progress.total_calories_burned if today_progress else None,
        },
        "profile_targets": {
            "target_calories": profile.target_calories if profile else None,
            "target_protein_g": profile.target_protein_g if profile else None,
            "target_fiber_g": profile.target_fiber_g if profile else None,
        } if profile else None,
    }))

    response = _get_client().messages.create(
        model=Config.CLAUDE_MODEL,
        max_tokens=1024,
        system=system_blocks,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "log_fitness_data"},
        messages=[{"role": "user", "content": message}],
    )
    _log_usage(response, "extract_intent")

    for block in response.content:
        if block.type == "tool_use" and block.name == "log_fitness_data":
            result = block.input
            logger.info(json.dumps({
                "event": "extract_intent_output",
                "intent": result.get("intent"),
                "estimated_calories": result.get("estimated_calories"),
                "estimated_protein": result.get("estimated_protein"),
                "estimated_fiber": result.get("estimated_fiber"),
                "feedback": result.get("immediate_feedback"),
            }))
            return result
    return {"intent": "unknown"}


def generate_daily_summary_message(summary: DailySummary, meals: list, profile: Optional[Profile] = None) -> str:
    """Generate a friendly daily summary message using Claude."""
    meal_list = "\n".join(
        f"- {m.meal_description} (~{m.estimated_calories} cal, {m.estimated_protein}g prot)"
        for m in meals
    )
    net_calories = summary.total_calories - summary.total_calories_burned

    target_section = ""
    if profile is not None:
        cal_delta = profile.target_calories - summary.total_calories
        prot_delta = profile.target_protein_g - summary.total_protein
        fiber_delta = profile.target_fiber_g - summary.total_fiber
        target_section = (
            f"\nMetas vs realidad:\n"
            f"- Calorías: {summary.total_calories}/{profile.target_calories} "
            f"({'+' if cal_delta < 0 else '-'}{abs(cal_delta)} cal)\n"
            f"- Proteína: {summary.total_protein}/{profile.target_protein_g}g "
            f"({'+' if prot_delta < 0 else '-'}{abs(prot_delta)}g)\n"
            f"- Fibra: {summary.total_fiber}/{profile.target_fiber_g}g "
            f"({'+' if fiber_delta < 0 else '-'}{abs(fiber_delta)}g)\n"
            f"- Meta del usuario: {profile.goal}"
        )

    prompt = f"""Genera un resumen diario amigable y motivador en español para el usuario basándote en estos datos:

Comidas del día:
{meal_list if meal_list else "No se registraron comidas"}

Resumen:
- Calorías consumidas: {summary.total_calories}
- Proteína total: {summary.total_protein}g
- Fibra total: {summary.total_fiber}g
- Calorías quemadas por ejercicio: {summary.total_calories_burned}
- Pasos: {summary.total_steps}
- Calorías netas: {net_calories}
- Comidas registradas: {summary.meal_count}
- Riesgo de hambre nocturna: {summary.hunger_risk()}{target_section}

El mensaje debe ser:
- En español, conversacional, máximo 5 oraciones
- Mencionar los números más relevantes
- Si hay metas, comparar contra ellas con honestidad (déficit, sobrepasarse, etc.)
- Dar 1 consejo concreto para mañana
- Terminar con un emoji motivador"""

    response = _get_client().messages.create(
        model=Config.CLAUDE_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    _log_usage(response, "generate_daily_summary_message")
    return response.content[0].text


def generate_weekly_trend_message(
    days: list[DailySummary],
    body_metrics: list[BodyMetrics],
    profile: Optional[Profile] = None,
) -> str:
    """Generate a weekly trend analysis message using Claude."""
    days_data = "\n".join(
        f"- {d.date}: {d.total_calories} cal, {d.total_protein}g prot, {d.total_fiber}g fibra, {d.total_steps} pasos"
        for d in days
    )
    metrics_data = "\n".join(
        f"- {m.date}: {m.weight_kg}kg"
        for m in body_metrics
        if m.weight_kg is not None
    )

    profile_section = ""
    if profile is not None:
        profile_section = (
            f"\nMetas del usuario:\n"
            f"- Meta: {profile.goal}\n"
            f"- Calorías diarias objetivo: {profile.target_calories}\n"
            f"- Proteína diaria objetivo: {profile.target_protein_g}g\n"
            f"- Peso inicial: {profile.baseline_weight_kg}kg ({profile.baseline_date})"
        )

    prompt = f"""Genera un análisis de tendencias semanal en español basándote en estos datos:

Datos diarios (últimos 7 días):
{days_data if days_data else "Sin datos"}

Peso registrado:
{metrics_data if metrics_data else "Sin registros de peso"}{profile_section}

El análisis debe:
- Estar en español, ser conversacional, máximo 6 oraciones
- Comparar el promedio semanal contra las metas si existen
- Identificar 1-2 tendencias positivas
- Identificar 1 área de mejora con sugerencia concreta
- Mencionar progreso de peso vs inicial si hay datos
- Terminar con motivación para la siguiente semana"""

    response = _get_client().messages.create(
        model=Config.CLAUDE_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    _log_usage(response, "generate_weekly_trend_message")
    return response.content[0].text
