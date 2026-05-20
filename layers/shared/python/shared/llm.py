import anthropic
from shared.config import Config
from shared.models import DailySummary, BodyMetrics

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
    return _client


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
- Motivadora pero honesta

Ejemplos de retroalimentación:
- Comida: "Buen desayuno. Estimé ~350 cal y 25g de proteína."
- Ejercicio: "Excelente rutina. Estimé ~400 cal quemadas."
- Peso: "Peso registrado. Vas bien con el seguimiento."
"""

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


def extract_intent(message: str) -> dict:
    """Extract structured fitness data from a user message using Claude with tool_use."""
    response = _get_client().messages.create(
        model=Config.CLAUDE_MODEL,
        max_tokens=1024,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "log_fitness_data"},
        messages=[{"role": "user", "content": message}],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "log_fitness_data":
            return block.input
    return {"intent": "unknown"}


def generate_daily_summary_message(summary: DailySummary, meals: list) -> str:
    """Generate a friendly daily summary message using Claude."""
    meal_list = "\n".join(
        f"- {m.meal_description} (~{m.estimated_calories} cal, {m.estimated_protein}g prot)"
        for m in meals
    )
    net_calories = summary.total_calories - summary.total_calories_burned

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
- Riesgo de hambre nocturna: {summary.hunger_risk()}

El mensaje debe ser:
- En español, conversacional, máximo 5 oraciones
- Mencionar los números más relevantes
- Dar 1 consejo concreto para mañana
- Terminar con un emoji motivador"""

    response = _get_client().messages.create(
        model=Config.CLAUDE_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def generate_weekly_trend_message(days: list[DailySummary], body_metrics: list[BodyMetrics]) -> str:
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

    prompt = f"""Genera un análisis de tendencias semanal en español basándote en estos datos:

Datos diarios (últimos 7 días):
{days_data if days_data else "Sin datos"}

Peso registrado:
{metrics_data if metrics_data else "Sin registros de peso"}

El análisis debe:
- Estar en español, ser conversacional, máximo 6 oraciones
- Identificar 1-2 tendencias positivas
- Identificar 1 área de mejora con sugerencia concreta
- Mencionar progreso de peso si hay datos
- Terminar con motivación para la siguiente semana"""

    response = _get_client().messages.create(
        model=Config.CLAUDE_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
