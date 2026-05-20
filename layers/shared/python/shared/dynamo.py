import boto3
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from shared.config import Config
from shared.models import MealLog, BodyMetrics, ExerciseLog, DailySummary

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(Config.TABLE_NAME)
    return _table


def _to_decimal(value) -> Decimal:
    return Decimal(str(value))


def _decimalize(obj):
    """Recursively convert floats/ints to Decimal for DynamoDB writes."""
    if isinstance(obj, float):
        return _to_decimal(obj)
    if isinstance(obj, dict):
        return {k: _decimalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimalize(v) for v in obj]
    return obj


def _from_decimal(obj):
    """Recursively convert Decimal back to float/int for application use."""
    if isinstance(obj, Decimal):
        if obj == obj.to_integral_value():
            return int(obj)
        return float(obj)
    if isinstance(obj, dict):
        return {k: _from_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_from_decimal(v) for v in obj]
    return obj


def save_meal(meal: MealLog) -> None:
    table = _get_table()
    table.put_item(Item=_decimalize(meal.to_dynamo()))


def save_body_metrics(metrics: BodyMetrics) -> None:
    table = _get_table()
    item = metrics.to_dynamo()
    # merge with existing record so partial updates (e.g. only weight) don't wipe other fields
    existing = get_body_metrics_for_date(metrics.user_id, metrics.date)
    if existing:
        existing_item = existing.to_dynamo()
        existing_item.update({k: v for k, v in item.items() if v is not None})
        item = existing_item
    table.put_item(Item=_decimalize(item))


def save_exercise(exercise: ExerciseLog) -> None:
    table = _get_table()
    table.put_item(Item=_decimalize(exercise.to_dynamo()))


def upsert_daily_summary(summary: DailySummary) -> None:
    table = _get_table()
    table.put_item(Item=_decimalize(summary.to_dynamo()))


def get_meals_for_date(user_id: str, date: str) -> list[MealLog]:
    table = _get_table()
    resp = table.query(
        KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
        ExpressionAttributeValues={
            ":pk": f"USER#{user_id}",
            ":prefix": f"MEAL#{date}",
        },
    )
    meals = []
    for item in resp.get("Items", []):
        item = _from_decimal(item)
        meals.append(MealLog(
            user_id=user_id,
            timestamp=item["SK"].split("#", 1)[1],
            meal_description=item.get("meal_description", ""),
            estimated_calories=item.get("estimated_calories", 0),
            estimated_protein=item.get("estimated_protein", 0),
            estimated_fiber=item.get("estimated_fiber", 0),
            satiety_score=item.get("satiety_score", 3),
        ))
    return meals


def get_exercises_for_date(user_id: str, date: str) -> list[ExerciseLog]:
    table = _get_table()
    resp = table.query(
        KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
        ExpressionAttributeValues={
            ":pk": f"USER#{user_id}",
            ":prefix": f"EXERCISE#{date}",
        },
    )
    exercises = []
    for item in resp.get("Items", []):
        item = _from_decimal(item)
        exercises.append(ExerciseLog(
            user_id=user_id,
            timestamp=item["SK"].split("#", 1)[1],
            exercise_description=item.get("exercise_description", ""),
            estimated_calories_burned=item.get("estimated_calories_burned", 0),
            steps=item.get("steps", 0),
        ))
    return exercises


def get_body_metrics_for_date(user_id: str, date: str) -> Optional[BodyMetrics]:
    table = _get_table()
    resp = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"BODY#{date}"})
    item = resp.get("Item")
    if not item:
        return None
    item = _from_decimal(item)
    return BodyMetrics(
        user_id=user_id,
        date=date,
        weight_kg=_to_decimal(item["weight_kg"]) if "weight_kg" in item else None,
        waist_inches=_to_decimal(item["waist_inches"]) if "waist_inches" in item else None,
        neck_inches=_to_decimal(item["neck_inches"]) if "neck_inches" in item else None,
        arms_inches=_to_decimal(item["arms_inches"]) if "arms_inches" in item else None,
    )


def get_daily_summary(user_id: str, date: str) -> Optional[DailySummary]:
    table = _get_table()
    resp = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"DAY#{date}"})
    item = resp.get("Item")
    if not item:
        return None
    item = _from_decimal(item)
    return DailySummary(
        user_id=user_id,
        date=date,
        total_calories=item.get("total_calories", 0),
        total_protein=item.get("total_protein", 0),
        total_fiber=item.get("total_fiber", 0),
        total_calories_burned=item.get("total_calories_burned", 0),
        total_steps=item.get("total_steps", 0),
        meal_count=item.get("meal_count", 0),
        avg_satiety=_to_decimal(item.get("avg_satiety", 0)),
    )


def get_body_metrics_range(user_id: str, start_date: str, end_date: str) -> list[BodyMetrics]:
    table = _get_table()
    resp = table.query(
        KeyConditionExpression="PK = :pk AND SK BETWEEN :start AND :end",
        ExpressionAttributeValues={
            ":pk": f"USER#{user_id}",
            ":start": f"BODY#{start_date}",
            ":end": f"BODY#{end_date}",
        },
    )
    metrics = []
    for item in resp.get("Items", []):
        item = _from_decimal(item)
        date = item["SK"].split("#", 1)[1]
        metrics.append(BodyMetrics(
            user_id=user_id,
            date=date,
            weight_kg=_to_decimal(item["weight_kg"]) if "weight_kg" in item else None,
            waist_inches=_to_decimal(item["waist_inches"]) if "waist_inches" in item else None,
            neck_inches=_to_decimal(item["neck_inches"]) if "neck_inches" in item else None,
            arms_inches=_to_decimal(item["arms_inches"]) if "arms_inches" in item else None,
        ))
    return metrics


def get_daily_summaries_range(user_id: str, start_date: str, end_date: str) -> list[DailySummary]:
    table = _get_table()
    resp = table.query(
        KeyConditionExpression="PK = :pk AND SK BETWEEN :start AND :end",
        ExpressionAttributeValues={
            ":pk": f"USER#{user_id}",
            ":start": f"DAY#{start_date}",
            ":end": f"DAY#{end_date}",
        },
    )
    summaries = []
    for item in resp.get("Items", []):
        item = _from_decimal(item)
        date = item["SK"].split("#", 1)[1]
        summaries.append(DailySummary(
            user_id=user_id,
            date=date,
            total_calories=item.get("total_calories", 0),
            total_protein=item.get("total_protein", 0),
            total_fiber=item.get("total_fiber", 0),
            total_calories_burned=item.get("total_calories_burned", 0),
            total_steps=item.get("total_steps", 0),
            meal_count=item.get("meal_count", 0),
            avg_satiety=_to_decimal(item.get("avg_satiety", 0)),
        ))
    return summaries


def compute_and_save_daily_summary(user_id: str, date: str) -> DailySummary:
    """Recompute daily summary from raw logs and persist it."""
    meals = get_meals_for_date(user_id, date)
    exercises = get_exercises_for_date(user_id, date)

    total_calories = sum(m.estimated_calories for m in meals)
    total_protein = sum(m.estimated_protein for m in meals)
    total_fiber = sum(m.estimated_fiber for m in meals)
    total_calories_burned = sum(e.estimated_calories_burned for e in exercises)
    total_steps = sum(e.steps for e in exercises)
    meal_count = len(meals)
    avg_satiety = (
        _to_decimal(sum(m.satiety_score for m in meals) / meal_count)
        .quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if meal_count > 0
        else Decimal("0")
    )

    summary = DailySummary(
        user_id=user_id,
        date=date,
        total_calories=total_calories,
        total_protein=total_protein,
        total_fiber=total_fiber,
        total_calories_burned=total_calories_burned,
        total_steps=total_steps,
        meal_count=meal_count,
        avg_satiety=avg_satiety,
    )
    upsert_daily_summary(summary)
    return summary
