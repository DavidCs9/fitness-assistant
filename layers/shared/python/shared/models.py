from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional


class IntentType(str, Enum):
    MEAL_LOG = "meal_log"
    BODY_METRICS = "body_metrics"
    EXERCISE_LOG = "exercise_log"
    QUERY_SUMMARY = "query_summary"
    QUERY_TREND = "query_trend"
    UNKNOWN = "unknown"


@dataclass
class MealLog:
    user_id: str
    timestamp: str
    meal_description: str
    estimated_calories: int
    estimated_protein: int
    estimated_fiber: int
    satiety_score: int

    def to_dynamo(self) -> dict:
        return {
            "PK": f"USER#{self.user_id}",
            "SK": f"MEAL#{self.timestamp}",
            "meal_description": self.meal_description,
            "estimated_calories": self.estimated_calories,
            "estimated_protein": self.estimated_protein,
            "estimated_fiber": self.estimated_fiber,
            "satiety_score": self.satiety_score,
            "entity_type": "meal",
        }


@dataclass
class BodyMetrics:
    user_id: str
    date: str
    weight_kg: Optional[Decimal] = None
    waist_inches: Optional[Decimal] = None
    neck_inches: Optional[Decimal] = None
    arms_inches: Optional[Decimal] = None

    def to_dynamo(self) -> dict:
        item = {
            "PK": f"USER#{self.user_id}",
            "SK": f"BODY#{self.date}",
            "entity_type": "body_metrics",
        }
        if self.weight_kg is not None:
            item["weight_kg"] = self.weight_kg
        if self.waist_inches is not None:
            item["waist_inches"] = self.waist_inches
        if self.neck_inches is not None:
            item["neck_inches"] = self.neck_inches
        if self.arms_inches is not None:
            item["arms_inches"] = self.arms_inches
        return item


@dataclass
class ExerciseLog:
    user_id: str
    timestamp: str
    exercise_description: str
    estimated_calories_burned: int
    steps: int

    def to_dynamo(self) -> dict:
        return {
            "PK": f"USER#{self.user_id}",
            "SK": f"EXERCISE#{self.timestamp}",
            "exercise_description": self.exercise_description,
            "estimated_calories_burned": self.estimated_calories_burned,
            "steps": self.steps,
            "entity_type": "exercise",
        }


@dataclass
class DailySummary:
    user_id: str
    date: str
    total_calories: int = 0
    total_protein: int = 0
    total_fiber: int = 0
    total_calories_burned: int = 0
    total_steps: int = 0
    meal_count: int = 0
    avg_satiety: Decimal = Decimal("0")

    def hunger_risk(self) -> str:
        if self.total_fiber < 15:
            return "alto"
        if self.total_fiber < 25:
            return "medio"
        return "bajo"

    def to_dynamo(self) -> dict:
        return {
            "PK": f"USER#{self.user_id}",
            "SK": f"DAY#{self.date}",
            "total_calories": self.total_calories,
            "total_protein": self.total_protein,
            "total_fiber": self.total_fiber,
            "total_calories_burned": self.total_calories_burned,
            "total_steps": self.total_steps,
            "meal_count": self.meal_count,
            "avg_satiety": self.avg_satiety,
            "entity_type": "daily_summary",
        }
