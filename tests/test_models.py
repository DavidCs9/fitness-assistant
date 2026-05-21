from decimal import Decimal
from shared.models import MealLog, ExerciseLog, BodyMetrics, DailySummary, Profile, IntentType


class TestMealLog:
    def test_to_dynamo_keys(self):
        meal = MealLog("123", "2024-01-01T12:00:00", "arroz con pollo", 500, 30, 5, 4)
        item = meal.to_dynamo()
        assert item["PK"] == "USER#123"
        assert item["SK"] == "MEAL#2024-01-01T12:00:00"
        assert item["entity_type"] == "meal"

    def test_to_dynamo_values(self):
        meal = MealLog("123", "2024-01-01T12:00:00", "tacos", 600, 25, 8, 5)
        item = meal.to_dynamo()
        assert item["estimated_calories"] == 600
        assert item["estimated_protein"] == 25
        assert item["estimated_fiber"] == 8
        assert item["satiety_score"] == 5


class TestExerciseLog:
    def test_to_dynamo_keys(self):
        ex = ExerciseLog("456", "2024-01-01T08:00:00", "correr 5km", 300, 6000)
        item = ex.to_dynamo()
        assert item["PK"] == "USER#456"
        assert item["SK"] == "EXERCISE#2024-01-01T08:00:00"
        assert item["entity_type"] == "exercise"

    def test_to_dynamo_values(self):
        ex = ExerciseLog("456", "2024-01-01T08:00:00", "pesas", 200, 0)
        item = ex.to_dynamo()
        assert item["estimated_calories_burned"] == 200
        assert item["steps"] == 0


class TestBodyMetrics:
    def test_to_dynamo_keys(self):
        m = BodyMetrics("789", "2024-01-01", weight_kg=Decimal("75.5"))
        item = m.to_dynamo()
        assert item["PK"] == "USER#789"
        assert item["SK"] == "BODY#2024-01-01"

    def test_optional_fields_excluded_when_none(self):
        m = BodyMetrics("789", "2024-01-01", weight_kg=Decimal("75.5"))
        item = m.to_dynamo()
        assert "weight_kg" in item
        assert "waist_inches" not in item
        assert "neck_inches" not in item
        assert "arms_inches" not in item

    def test_all_fields_included(self):
        m = BodyMetrics(
            "789", "2024-01-01",
            weight_kg=Decimal("75.5"),
            waist_inches=Decimal("32.0"),
            neck_inches=Decimal("15.0"),
            arms_inches=Decimal("13.5"),
        )
        item = m.to_dynamo()
        assert "waist_inches" in item
        assert "neck_inches" in item
        assert "arms_inches" in item


class TestDailySummary:
    def test_to_dynamo_keys(self):
        s = DailySummary("123", "2024-01-01")
        item = s.to_dynamo()
        assert item["PK"] == "USER#123"
        assert item["SK"] == "DAY#2024-01-01"
        assert item["entity_type"] == "daily_summary"

    def test_hunger_risk_high(self):
        s = DailySummary("123", "2024-01-01", total_fiber=10)
        assert s.hunger_risk() == "alto"

    def test_hunger_risk_medium(self):
        s = DailySummary("123", "2024-01-01", total_fiber=20)
        assert s.hunger_risk() == "medio"

    def test_hunger_risk_low(self):
        s = DailySummary("123", "2024-01-01", total_fiber=30)
        assert s.hunger_risk() == "bajo"

    def test_hunger_risk_boundary_15(self):
        # exactly 15 → medio (not alto)
        s = DailySummary("123", "2024-01-01", total_fiber=15)
        assert s.hunger_risk() == "medio"

    def test_hunger_risk_boundary_25(self):
        # exactly 25 → bajo (not medio)
        s = DailySummary("123", "2024-01-01", total_fiber=25)
        assert s.hunger_risk() == "bajo"


class TestIntentType:
    def test_values(self):
        assert IntentType.MEAL_LOG == "meal_log"
        assert IntentType.EXERCISE_LOG == "exercise_log"
        assert IntentType.BODY_METRICS == "body_metrics"
        assert IntentType.QUERY_SUMMARY == "query_summary"
        assert IntentType.QUERY_TREND == "query_trend"
        assert IntentType.UNKNOWN == "unknown"
