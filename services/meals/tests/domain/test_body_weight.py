from datetime import date, timedelta

import pytest

from domain.body_weight import GoalProgress, WeightRecord
from domain.errors import MealError
from domain.nutrition_goal import NutritionGoal, Policy
from tests.domain.factories import EATER

TODAY = date(2026, 10, 12)


def records(*kgs_by_days_ago):
    return tuple(WeightRecord(EATER, TODAY - timedelta(days=d), kg) for d, kg in sorted(kgs_by_days_ago, reverse=True))


def progress(policy=Policy.BULK, target=70.0, *recs):
    goal = NutritionGoal(EATER, policy, target_weight_kg=target)
    return GoalProgress(goal, records(*recs), TODAY)


def test_目標体重まであと何kgか():
    p = progress(Policy.BULK, 70.0, (14, 66.0), (0, 67.0))
    assert p.remaining_kg == pytest.approx(3.0)


def test_1週間あたりの変化と_目標までの週数():
    p = progress(Policy.BULK, 70.0, (14, 66.0), (0, 67.0))
    assert p.weekly_change_kg == pytest.approx(0.5)
    assert p.weeks_to_goal == pytest.approx(6.0)
    assert p.on_track is True


def test_逆向きに動いているなら目標までの週数は出さない():
    p = progress(Policy.BULK, 70.0, (14, 67.0), (0, 66.0))
    assert p.weeks_to_goal is None and p.on_track is False


def test_記録が1週間に満たなければ変化は出さない():
    p = progress(Policy.BULK, 70.0, (3, 66.0), (0, 67.0))
    assert p.weekly_change_kg is None and p.weeks_to_goal is None


def test_4週間より前の記録は変化の計算に使わない():
    p = progress(Policy.MAINTAIN, None, (60, 60.0), (14, 67.0), (0, 67.0))
    assert p.weekly_change_kg == pytest.approx(0) and p.on_track is True
    assert p.remaining_kg is None  # 目標体重なし


def test_体重の範囲を確かめる():
    with pytest.raises(MealError):
        WeightRecord(EATER, TODAY, 10)
