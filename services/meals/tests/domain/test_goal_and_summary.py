from dataclasses import astuple
from datetime import date

import pytest

from domain.errors import MealError
from domain.meal_template import MealTemplate
from domain.nutrition_goal import DailyTarget, NutritionGoal, Policy, Target
from domain.summary import DailySummary, WeeklyReview
from domain.values import DayType, EatenOn, MealSlot, Nutrition, NutritionGap, Source
from tests.domain.factories import EATER, approx, lunch

GOAL = NutritionGoal(
    eater_id=EATER,
    policy=Policy.BULK,
    body_weight_kg=70,
    protein_per_kg=2.0,
    training_day=DailyTarget(kcal=2800, fat_g=70, carbs_g=380),
    rest_day=DailyTarget(kcal=2400, fat_g=70, carbs_g=280),
)


def test_目標は日の種類で変わり_たんぱく質は体重から決まる():
    assert GOAL.target_for(DayType.TRAINING) == Target(2800, 140, 70, 380)
    assert GOAL.target_for(DayType.REST) == Target(2400, 140, 70, 280)


def test_方針だけの目標もあり_分かる項目だけ残りを出す():
    protein_only = NutritionGoal(EATER, Policy.BULK, body_weight_kg=70, protein_per_kg=2.0)
    summary = DailySummary(date(2026, 10, 12), DayType.REST, (lunch(),), protein_only)
    assert summary.remaining == NutritionGap(None, 113, None, None)
    policy_only = NutritionGoal(EATER, Policy.MAINTAIN)
    assert DailySummary(date(2026, 10, 12), DayType.REST, (lunch(),), policy_only).remaining == NutritionGap(
        None, None, None, None)


def test_筋トレの日と休みの日の目標は両方そろえる():
    with pytest.raises(MealError):
        NutritionGoal(EATER, Policy.BULK, training_day=DailyTarget(2800, 70, 380))


def test_体重は0より大きい():
    with pytest.raises(MealError):
        NutritionGoal(EATER, Policy.CUT, 0, 2.0, DailyTarget(1, 1, 1), DailyTarget(1, 1, 1))


def test_いつものから食事を作る():
    template = MealTemplate.from_meal(lunch(), "いつもの昼")
    dinner = EatenOn(date(2026, 10, 13), MealSlot.DINNER)
    meal = template.to_meal("meal-9", dinner)
    assert (meal.id, meal.eaten_on, meal.source) == ("meal-9", dinner, Source.TEMPLATE)
    assert meal.items == lunch().items


def test_1日のまとめは合計と残りを出す():
    summary = DailySummary(date(2026, 10, 12), DayType.REST, (lunch(),), GOAL)
    assert summary.total == Nutrition(420, 27, 2.1, 74)
    assert astuple(summary.remaining) == approx(NutritionGap(1980, 113, 67.9, 206))


def test_目標が未設定なら残りは出さない():
    summary = DailySummary(date(2026, 10, 12), DayType.REST, (lunch(),), None)
    assert summary.target is None and summary.remaining is None


def test_週の平均は記録した日だけで出す():
    days = (
        DailySummary(date(2026, 10, 12), DayType.REST, (lunch(), lunch("meal-2")), GOAL),
        DailySummary(date(2026, 10, 13), DayType.TRAINING, (), GOAL),  # 記録なし
        DailySummary(date(2026, 10, 14), DayType.TRAINING, (lunch("meal-3"),), GOAL),
    )
    review = WeeklyReview(days)
    assert len(review.recorded_days) == 2
    assert astuple(review.average) == approx(Nutrition(630, 40.5, 3.15, 111))
    assert astuple(review.average_target) == approx(Nutrition(2600, 140, 70, 330))
    assert astuple(review.gap) == approx(NutritionGap(-1970, -99.5, -66.85, -219))
