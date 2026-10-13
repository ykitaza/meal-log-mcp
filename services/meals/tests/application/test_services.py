from dataclasses import astuple
from datetime import date
from itertools import count

import pytest

from application.commands import MealChanges, NewItem, NewMeal
from application.goals import GoalService
from application.meals import MealService
from application.summaries import SummaryService
from application.templates import TemplateService
from domain.errors import MealError, NotFound
from domain.nutrition_goal import DailyTarget, NutritionGoal, Policy
from domain.values import DayType, EatenOn, EaterId, MealSlot, Nutrition, Quantity, Source, Unit
from infrastructure.memory_repositories import (
    InMemoryDayTypeRepository,
    InMemoryGoalRepository,
    InMemoryMealRepository,
    InMemoryMealTemplateRepository,
)
from infrastructure.subject_as_eater_id import SubjectAsEaterId
from tests.domain.factories import approx

DAY = date(2026, 10, 12)
LUNCH = EatenOn(DAY, MealSlot.LUNCH)
RICE = NewItem("白米", Quantity(200, Unit.GRAM), Nutrition(312, 5, 0.6, 74))
CHICKEN = NewItem("鶏むね肉", Quantity(100, Unit.GRAM), Nutrition(108, 22, 1.5, 0))
GOAL = NutritionGoal(
    EaterId("ignored"), Policy.BULK, 70, 2.0, DailyTarget(2800, 70, 380), DailyTarget(2400, 70, 280))


@pytest.fixture
def app():
    eaters, meals = SubjectAsEaterId(), InMemoryMealRepository()
    goals, day_types = InMemoryGoalRepository(), InMemoryDayTypeRepository()
    numbers = count(1)
    ids = lambda: f"id{next(numbers)}"  # noqa: E731
    return {
        "meals": MealService(eaters, meals, ids),
        "templates": TemplateService(eaters, meals, InMemoryMealTemplateRepository(), ids),
        "goals": GoalService(eaters, goals, day_types),
        "summaries": SummaryService(eaters, meals, goals, day_types),
    }


async def record_lunch(app, subject="alice", eaten_on=LUNCH):
    return await app["meals"].record(subject, NewMeal(eaten_on, (RICE, CHICKEN), "白米と鶏むね肉", Source.PHOTO))


@pytest.mark.anyio
async def test_記録すると_id_が付き_読める(app):
    meal = await record_lunch(app)
    assert [item.id for item in meal.items] == ["id1", "id2"]
    assert meal.id == "id3"
    assert await app["meals"].get("alice", meal.id) == meal


@pytest.mark.anyio
async def test_ほかの人の食事は読めず消せない(app):
    meal = await record_lunch(app, "alice")
    with pytest.raises(NotFound):
        await app["meals"].get("bob", meal.id)
    with pytest.raises(NotFound):
        await app["meals"].delete("bob", meal.id)
    assert await app["meals"].get("alice", meal.id)


@pytest.mark.anyio
async def test_まとめて記録し_1件でも不正なら何も保存しない(app):
    good = NewMeal(LUNCH, (RICE,), "白米", Source.PHOTO)
    bad = NewMeal(LUNCH, (), "空", Source.PHOTO)
    with pytest.raises(MealError):
        await app["meals"].record_many("alice", [good, bad])
    assert await app["meals"].list("alice", DAY, DAY) == []


@pytest.mark.anyio
async def test_期間と区分で絞って読む(app):
    await record_lunch(app)
    await record_lunch(app, eaten_on=EatenOn(DAY, MealSlot.BREAKFAST))
    await record_lunch(app, eaten_on=EatenOn(date(2026, 10, 13), MealSlot.LUNCH))
    assert [m.eaten_on.slot for m in await app["meals"].list("alice", DAY, DAY)] == [MealSlot.BREAKFAST, MealSlot.LUNCH]
    assert len(await app["meals"].list("alice", DAY, date(2026, 10, 13), MealSlot.LUNCH)) == 2


@pytest.mark.anyio
async def test_まとめて修正する(app):
    meal = await record_lunch(app)
    dinner = EatenOn(DAY, MealSlot.DINNER)
    changes = MealChanges(amounts={"id1": 100}, add=(RICE,), remove=("id2",), eaten_on=dinner)
    updated = await app["meals"].update("alice", meal.id, changes)
    assert [(i.id, i.quantity.amount) for i in updated.items] == [("id1", 100), ("id4", 200)]
    assert updated.eaten_on == dinner
    assert await app["meals"].get("alice", meal.id) == updated


@pytest.mark.anyio
async def test_昨日と同じを記録する(app):
    meal = await record_lunch(app)
    copy = await app["meals"].copy("alice", meal.id, EatenOn(date(2026, 10, 13), MealSlot.LUNCH))
    assert copy.id != meal.id and copy.source == Source.COPY


@pytest.mark.anyio
async def test_いつものを保存して名前で記録する(app):
    meal = await record_lunch(app)
    await app["templates"].save("alice", meal.id, "いつもの昼")
    recorded = await app["templates"].record("alice", "いつもの昼", EatenOn(date(2026, 10, 13), MealSlot.LUNCH))
    assert recorded.source == Source.TEMPLATE and recorded.items == meal.items


@pytest.mark.anyio
async def test_ないいつものは保存してある名前を知らせる(app):
    await app["templates"].save("alice", (await record_lunch(app)).id, "いつもの昼")
    with pytest.raises(NotFound, match="いつもの昼"):
        await app["templates"].record("alice", "朝のセット", LUNCH)


@pytest.mark.anyio
async def test_目標はトークンの本人のものとして保存する(app):
    goal = await app["goals"].set_goals("alice", GOAL)
    assert goal.eater_id == EaterId("alice")


@pytest.mark.anyio
async def test_今日の残りは日の種類の目標から計算する(app):
    await record_lunch(app)
    await app["goals"].set_goals("alice", GOAL)
    assert (await app["summaries"].daily("alice", DAY)).remaining.kcal == pytest.approx(2400 - 420)  # 決めていない日は休み
    await app["goals"].set_day_type("alice", DAY, DayType.TRAINING)
    assert (await app["summaries"].daily("alice", DAY)).remaining.kcal == pytest.approx(2800 - 420)


@pytest.mark.anyio
async def test_目標を決めていなければ残りは出ない(app):
    await record_lunch(app)
    assert (await app["summaries"].daily("alice", DAY)).remaining is None


@pytest.mark.anyio
async def test_週のふり返りは7日分で_平均は記録した日だけ(app):
    await record_lunch(app)
    await record_lunch(app, eaten_on=EatenOn(date(2026, 10, 10), MealSlot.LUNCH))
    review = await app["summaries"].weekly("alice", DAY)
    assert [d.day for d in review.days] == [date(2026, 10, n) for n in range(6, 13)]
    assert len(review.recorded_days) == 2
    assert astuple(review.average) == approx(Nutrition(420, 27, 2.1, 74))
