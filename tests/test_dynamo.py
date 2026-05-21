from decimal import Decimal
from unittest.mock import patch, MagicMock
from shared import dynamo
from shared.models import MealLog, ExerciseLog, DailySummary


class TestDecimalize:
    def test_converts_float(self):
        assert dynamo._decimalize(1.5) == Decimal("1.5")

    def test_leaves_int_unchanged(self):
        assert dynamo._decimalize(5) == 5

    def test_converts_nested_dict(self):
        result = dynamo._decimalize({"a": 1.5, "b": 2})
        assert result["a"] == Decimal("1.5")
        assert result["b"] == 2

    def test_converts_list(self):
        result = dynamo._decimalize([1.5, 2.0])
        assert result == [Decimal("1.5"), Decimal("2.0")]


class TestFromDecimal:
    def test_converts_whole_decimal_to_int(self):
        assert dynamo._from_decimal(Decimal("5.0")) == 5
        assert isinstance(dynamo._from_decimal(Decimal("5.0")), int)

    def test_converts_fractional_decimal_to_float(self):
        assert dynamo._from_decimal(Decimal("5.5")) == 5.5
        assert isinstance(dynamo._from_decimal(Decimal("5.5")), float)

    def test_leaves_non_decimal_unchanged(self):
        assert dynamo._from_decimal("hello") == "hello"
        assert dynamo._from_decimal(42) == 42

    def test_converts_nested_dict(self):
        result = dynamo._from_decimal({"a": Decimal("3.0"), "b": Decimal("3.5")})
        assert result["a"] == 3
        assert result["b"] == 3.5


class TestComputeAndSaveDailySummary:
    def _make_meal(self, calories, protein, fiber, satiety):
        return MealLog("u1", "2024-01-01T12:00:00", "comida", calories, protein, fiber, satiety)

    def _make_exercise(self, calories_burned, steps):
        return ExerciseLog("u1", "2024-01-01T08:00:00", "ejercicio", calories_burned, steps)

    @patch("shared.dynamo.upsert_daily_summary")
    @patch("shared.dynamo.get_exercises_for_date")
    @patch("shared.dynamo.get_meals_for_date")
    def test_sums_calories_and_protein(self, mock_meals, mock_exercises, mock_upsert):
        mock_meals.return_value = [
            self._make_meal(400, 20, 5, 3),
            self._make_meal(600, 30, 10, 4),
        ]
        mock_exercises.return_value = []

        summary = dynamo.compute_and_save_daily_summary("u1", "2024-01-01")

        assert summary.total_calories == 1000
        assert summary.total_protein == 50
        assert summary.total_fiber == 15
        assert summary.meal_count == 2

    @patch("shared.dynamo.upsert_daily_summary")
    @patch("shared.dynamo.get_exercises_for_date")
    @patch("shared.dynamo.get_meals_for_date")
    def test_sums_exercise_data(self, mock_meals, mock_exercises, mock_upsert):
        mock_meals.return_value = []
        mock_exercises.return_value = [
            self._make_exercise(300, 5000),
            self._make_exercise(100, 2000),
        ]

        summary = dynamo.compute_and_save_daily_summary("u1", "2024-01-01")

        assert summary.total_calories_burned == 400
        assert summary.total_steps == 7000

    @patch("shared.dynamo.upsert_daily_summary")
    @patch("shared.dynamo.get_exercises_for_date")
    @patch("shared.dynamo.get_meals_for_date")
    def test_avg_satiety(self, mock_meals, mock_exercises, mock_upsert):
        mock_meals.return_value = [
            self._make_meal(300, 20, 5, 2),
            self._make_meal(500, 30, 8, 4),
        ]
        mock_exercises.return_value = []

        summary = dynamo.compute_and_save_daily_summary("u1", "2024-01-01")

        assert summary.avg_satiety == Decimal("3.0")

    @patch("shared.dynamo.upsert_daily_summary")
    @patch("shared.dynamo.get_exercises_for_date")
    @patch("shared.dynamo.get_meals_for_date")
    def test_no_meals_gives_zero_avg_satiety(self, mock_meals, mock_exercises, mock_upsert):
        mock_meals.return_value = []
        mock_exercises.return_value = []

        summary = dynamo.compute_and_save_daily_summary("u1", "2024-01-01")

        assert summary.avg_satiety == Decimal("0")
        assert summary.meal_count == 0

    @patch("shared.dynamo.upsert_daily_summary")
    @patch("shared.dynamo.get_exercises_for_date")
    @patch("shared.dynamo.get_meals_for_date")
    def test_calls_upsert(self, mock_meals, mock_exercises, mock_upsert):
        mock_meals.return_value = []
        mock_exercises.return_value = []

        dynamo.compute_and_save_daily_summary("u1", "2024-01-01")

        mock_upsert.assert_called_once()
