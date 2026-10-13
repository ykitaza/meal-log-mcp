import pytest

from domain.errors import MealError
from domain.goal_suggestion import BodyProfile, DailyActivity, GoalPlan, Sex, suggest_goal
from domain.nutrition_goal import Policy, Target
from domain.values import DayType
from tests.domain.factories import EATER

PROFILE = BodyProfile(Sex.MALE, age=30, height_cm=172, weight_kg=67, daily_activity=DailyActivity.LOW,
                      training_minutes=60)


def test_基礎代謝は_Mifflin_St_Jeor_の式():
    # 10×67 + 6.25×172 − 5×30 + 5 = 1600
    assert PROFILE.basal_metabolism() == 1600
    assert BodyProfile(Sex.FEMALE, 30, 172, 67, DailyActivity.LOW, 60).basal_metabolism() == 1434
    assert BodyProfile(Sex.UNSPECIFIED, 30, 172, 67, DailyActivity.LOW, 60).basal_metabolism() == 1517  # 中間


def test_筋トレの日は筋トレの分だけ多く消費する():
    assert PROFILE.rest_day_expenditure() == pytest.approx(1920)  # 1600 × 1.2
    assert PROFILE.training_expenditure() == pytest.approx(268)  # (5 − 1) × 67kg × 1時間


def test_増量の目標():
    goal = suggest_goal(EATER, PROFILE, GoalPlan(Policy.BULK, pace_kg_per_week=0.25, protein_per_kg=2.0)).goal
    rest, training = goal.target_for(DayType.REST), goal.target_for(DayType.TRAINING)
    assert rest.kcal == 2200  # 1920 + 0.25 × 7700 / 7（275）= 2195 → 10kcal 単位
    assert training.kcal == 2460  # 2195 + 268 = 2463
    assert rest.protein_g == training.protein_g == 134  # 67 × 2.0
    assert rest.fat_g == 61  # 2200 × 25% / 9
    assert rest.carbs_g == 279  # (2200 − 134×4 − 61×9) / 4


def test_減量は消費より少なくする():
    goal = suggest_goal(EATER, PROFILE, GoalPlan(Policy.CUT, pace_kg_per_week=0.5, protein_per_kg=2.2)).goal
    assert goal.target_for(DayType.REST).kcal == 1370  # 1920 − 550


@pytest.mark.parametrize("kwargs", [
    {"age": 10}, {"height_cm": 50}, {"weight_kg": 500}, {"training_minutes": -1},
])
def test_体のデータの範囲を確かめる(kwargs):
    args = dict(sex=Sex.MALE, age=30, height_cm=172, weight_kg=67, daily_activity=DailyActivity.LOW,
                training_minutes=60)
    with pytest.raises(MealError):
        BodyProfile(**{**args, **kwargs})


@pytest.mark.parametrize("plan", [
    dict(policy=Policy.MAINTAIN, pace_kg_per_week=0.25, protein_per_kg=2.0),
    dict(policy=Policy.BULK, pace_kg_per_week=0, protein_per_kg=2.0),
    dict(policy=Policy.BULK, pace_kg_per_week=0.25, protein_per_kg=5),
])
def test_計画の範囲を確かめる(plan):
    with pytest.raises(MealError):
        GoalPlan(**plan)


def test_方針だけなら数字の目標は出さない():
    suggestion = suggest_goal(EATER, BodyProfile(), GoalPlan(Policy.MAINTAIN))
    assert suggestion.goal.target_for(DayType.REST) == Target()
    assert any("体重" in note for note in suggestion.notes)


def test_体重だけならたんぱく質の目標だけ出す():
    suggestion = suggest_goal(EATER, BodyProfile(weight_kg=67), GoalPlan(Policy.BULK, 0.25))
    assert suggestion.goal.target_for(DayType.REST) == Target(protein_g=134)
    assert any("kcal" in note for note in suggestion.notes)


def test_筋トレの時間が分からなければ筋トレの日も休みの日と同じ():
    profile = BodyProfile(Sex.MALE, 30, 172, 67, DailyActivity.LOW)
    goal = suggest_goal(EATER, profile, GoalPlan(Policy.MAINTAIN)).goal
    assert goal.target_for(DayType.TRAINING) == goal.target_for(DayType.REST)
