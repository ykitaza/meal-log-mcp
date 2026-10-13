"""リポジトリの約束（ports.py）を、メモリー版と DynamoDB 版の両方で確かめる。

DynamoDB は moto（偽物）で動かす。テーブルの形は CDK と同じにしておく。
"""

from datetime import date

import boto3
import pytest
from moto import mock_aws

from domain.body_weight import WeightRecord
from domain.meal_template import MealTemplate
from domain.nutrition_goal import DailyTarget, EatingStyle, NutritionGoal, Policy
from domain.values import DayType, EatenOn, EaterId, MealSlot
from infrastructure import dynamodb_repositories as dynamo
from infrastructure import memory_repositories as memory
from tests.domain.factories import EATER, lunch

TABLE = "meals-test"
OTHER = EaterId("someone-else")


@pytest.fixture(params=["memory", "dynamodb"])
def repos(request, monkeypatch):
    if request.param == "memory":
        yield memory.InMemoryMealRepository(), memory.InMemoryMealTemplateRepository(), \
            memory.InMemoryGoalRepository(), memory.InMemoryDayTypeRepository(), memory.InMemoryWeightRepository()
        return
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-northeast-1")
    with mock_aws():
        boto3.client("dynamodb").create_table(
            TableName=TABLE,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": n, "AttributeType": "S"} for n in ("pk", "sk", "day_key")],
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
            LocalSecondaryIndexes=[{
                "IndexName": dynamo.BY_DAY_INDEX,
                "KeySchema": [
                    {"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "day_key", "KeyType": "RANGE"}],
                "Projection": {"ProjectionType": "ALL"},
            }],
        )
        yield dynamo.DynamoDBMealRepository(TABLE), dynamo.DynamoDBMealTemplateRepository(TABLE), \
            dynamo.DynamoDBGoalRepository(TABLE), dynamo.DynamoDBDayTypeRepository(TABLE), \
            dynamo.DynamoDBWeightRepository(TABLE)


@pytest.mark.anyio
async def test_食事を保存して読み_消せる(repos):
    meals = repos[0]
    meal = lunch()
    await meals.save(meal)
    assert await meals.get(EATER, meal.id) == meal
    assert await meals.get(OTHER, meal.id) is None  # ほかの人からは見えない
    await meals.delete(EATER, meal.id)
    assert await meals.get(EATER, meal.id) is None


@pytest.mark.anyio
async def test_期間の食事を日付と区分の順で返す(repos):
    meals = repos[0]
    await meals.save(lunch("dinner-11", EatenOn(date(2026, 10, 11), MealSlot.DINNER)))
    await meals.save(lunch("lunch-12", EatenOn(date(2026, 10, 12), MealSlot.LUNCH)))
    await meals.save(lunch("breakfast-12", EatenOn(date(2026, 10, 12), MealSlot.BREAKFAST)))
    await meals.save(lunch("lunch-13", EatenOn(date(2026, 10, 13), MealSlot.LUNCH)))
    await meals.save(lunch("other", EatenOn(date(2026, 10, 12), MealSlot.LUNCH), eater=OTHER))

    found = await meals.find(EATER, date(2026, 10, 11), date(2026, 10, 12))
    assert [m.id for m in found] == ["dinner-11", "breakfast-12", "lunch-12"]
    assert [m.id for m in await meals.find(EATER, date(2026, 10, 1), date(2026, 10, 31), MealSlot.LUNCH)] == [
        "lunch-12", "lunch-13"]


@pytest.mark.anyio
async def test_日時を移すと期間の検索にも反映される(repos):
    meals = repos[0]
    meal = lunch()
    await meals.save(meal)
    await meals.save(meal.move_to(EatenOn(date(2026, 10, 20), MealSlot.DINNER)))
    assert await meals.find(EATER, date(2026, 10, 12), date(2026, 10, 12)) == []
    assert len(await meals.find(EATER, date(2026, 10, 20), date(2026, 10, 20))) == 1


@pytest.mark.anyio
async def test_いつものは名前で上書きし_本人の分だけ一覧する(repos):
    templates = repos[1]
    await templates.save(MealTemplate.from_meal(lunch(), "いつもの昼"))
    await templates.save(MealTemplate.from_meal(lunch(), "いつもの昼"))
    await templates.save(MealTemplate.from_meal(lunch(eater=OTHER), "ほかの人の"))
    assert [t.name for t in await templates.list(EATER)] == ["いつもの昼"]
    assert await templates.get(EATER, "いつもの昼") == MealTemplate.from_meal(lunch(), "いつもの昼")


@pytest.mark.anyio
async def test_目標と日の種類(repos):
    goals, day_types = repos[2], repos[3]
    goal = NutritionGoal(
        EATER, Policy.CUT, 70.5, 2.0, DailyTarget(2200, 60, 250), DailyTarget(1900, 60, 180),
        EatingStyle.CONVENIENCE_STORE, target_weight_kg=65)
    await goals.save(goal)
    assert await goals.get(EATER) == goal
    assert await goals.get(OTHER) is None
    await day_types.set(EATER, date(2026, 10, 12), DayType.TRAINING)
    assert await day_types.get(EATER, date(2026, 10, 12)) == DayType.TRAINING
    assert await day_types.get(EATER, date(2026, 10, 13)) is None


@pytest.mark.anyio
async def test_体重は日付ごとに上書きし_期間で日付の順に返す(repos):
    weights = repos[4]
    await weights.save(WeightRecord(EATER, date(2026, 10, 12), 67.0))
    await weights.save(WeightRecord(EATER, date(2026, 10, 1), 66.0))
    await weights.save(WeightRecord(EATER, date(2026, 10, 12), 67.4))  # 同じ日は上書き
    await weights.save(WeightRecord(OTHER, date(2026, 10, 5), 80.0))
    found = await weights.find(EATER, date(2026, 10, 1), date(2026, 10, 12))
    assert [(r.day.day, r.kg) for r in found] == [(1, 66.0), (12, 67.4)]
    assert await weights.find(EATER, date(2026, 10, 2), date(2026, 10, 11)) == []
