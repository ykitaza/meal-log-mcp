"""リポジトリの実装（Lambda 用）。meals 専用の1つのテーブルに、種類の違う項目をまとめて置く。

  pk（パーティションキー）  sk（ソートキー）        中身
  EATER#<食べた人>          MEAL#<食事の id>         食事。day_key（食べた日＋区分の順番）も持つ
  EATER#<食べた人>          TEMPLATE#<名前>          いつもの
  EATER#<食べた人>          GOAL                     目標
  EATER#<食べた人>          DAYTYPE#<日付>           日の種類
  EATER#<食べた人>          WEIGHT#<日付>            体重の記録（sk が日付順に並ぶので、期間で探せる）

pk が食べた人なので、どの読み書きも本人の項目にしか届かない。
期間で食事を探すときは、ローカルセカンダリインデックス by_day（ソートキーは day_key）を使う。
day_key は食事の項目にしかないので、インデックスには食事だけが入る。
集約は JSON の文字列（data）で保存する（DynamoDB の数値は Decimal で返り、扱いが面倒なため）。
boto3 は同期なので、呼び出しをスレッドに逃がして async にする（Lambda ではスレッドが使える）。
"""

import json
from datetime import date
from functools import partial

import anyio

from domain.body_weight import WeightRecord
from domain.meal import Meal
from domain.meal_template import MealTemplate
from domain.nutrition_goal import NutritionGoal
from domain.values import DayType, EaterId, MealSlot
from infrastructure.serialization import (
    goal_from_dict,
    goal_to_dict,
    meal_from_dict,
    meal_to_dict,
    template_from_dict,
    template_to_dict,
)

BY_DAY_INDEX = "by_day"
SLOT_ORDER = list(MealSlot)


def _pk(eater_id: EaterId) -> str:
    return f"EATER#{eater_id.value}"


def _day_key(day: date, slot: MealSlot) -> str:
    return f"{day.isoformat()}#{SLOT_ORDER.index(slot)}"


class _Table:
    def __init__(self, table_name: str):
        import boto3  # Lambda の実行環境に入っている

        self.table = boto3.resource("dynamodb").Table(table_name)

    async def _call(self, method, **kwargs) -> dict:
        return await anyio.to_thread.run_sync(partial(method, **kwargs))

    async def put(self, eater_id: EaterId, sk: str, data: dict, **attributes) -> None:
        item = {"pk": _pk(eater_id), "sk": sk, "data": json.dumps(data), **attributes}
        await self._call(self.table.put_item, Item=item)

    async def get(self, eater_id: EaterId, sk: str) -> dict | None:
        item = (await self._call(self.table.get_item, Key={"pk": _pk(eater_id), "sk": sk})).get("Item")
        return None if item is None else json.loads(item["data"])

    async def delete(self, eater_id: EaterId, sk: str) -> None:
        await self._call(self.table.delete_item, Key={"pk": _pk(eater_id), "sk": sk})

    async def query(self, **kwargs) -> list[dict]:
        return [json.loads(item["data"]) for item in await self.query_items(**kwargs)]

    async def query_items(self, **kwargs) -> list[dict]:
        items, start_key = [], None
        while True:  # 1回の応答は 1MB までなので、続きがあれば読み続ける
            continuation = {"ExclusiveStartKey": start_key} if start_key else {}
            page = await self._call(self.table.query, **kwargs, **continuation)
            items += page["Items"]
            start_key = page.get("LastEvaluatedKey")
            if not start_key:
                return items


class DynamoDBMealRepository:
    def __init__(self, table_name: str):
        self.table = _Table(table_name)

    async def save(self, meal: Meal) -> None:
        day_key = _day_key(meal.eaten_on.day, meal.eaten_on.slot)
        await self.table.put(meal.eater_id, f"MEAL#{meal.id}", meal_to_dict(meal), day_key=day_key)

    async def get(self, eater_id: EaterId, meal_id: str) -> Meal | None:
        data = await self.table.get(eater_id, f"MEAL#{meal_id}")
        return None if data is None else meal_from_dict(data)

    async def delete(self, eater_id: EaterId, meal_id: str) -> None:
        await self.table.delete(eater_id, f"MEAL#{meal_id}")

    async def find(self, eater_id: EaterId, start: date, end: date, slot: MealSlot | None = None) -> list[Meal]:
        from boto3.dynamodb.conditions import Key

        condition = Key("pk").eq(_pk(eater_id)) & Key("day_key").between(
            _day_key(start, SLOT_ORDER[0]), _day_key(end, SLOT_ORDER[-1]))
        found = await self.table.query(IndexName=BY_DAY_INDEX, KeyConditionExpression=condition)
        meals = [meal_from_dict(d) for d in found]
        return [m for m in meals if slot is None or m.eaten_on.slot == slot]


class DynamoDBMealTemplateRepository:
    def __init__(self, table_name: str):
        self.table = _Table(table_name)

    async def save(self, template: MealTemplate) -> None:
        await self.table.put(template.eater_id, f"TEMPLATE#{template.name}", template_to_dict(template))

    async def get(self, eater_id: EaterId, name: str) -> MealTemplate | None:
        data = await self.table.get(eater_id, f"TEMPLATE#{name}")
        return None if data is None else template_from_dict(data)

    async def list(self, eater_id: EaterId) -> list[MealTemplate]:
        from boto3.dynamodb.conditions import Key

        condition = Key("pk").eq(_pk(eater_id)) & Key("sk").begins_with("TEMPLATE#")
        return [template_from_dict(d) for d in await self.table.query(KeyConditionExpression=condition)]


class DynamoDBGoalRepository:
    def __init__(self, table_name: str):
        self.table = _Table(table_name)

    async def save(self, goal: NutritionGoal) -> None:
        await self.table.put(goal.eater_id, "GOAL", goal_to_dict(goal))

    async def get(self, eater_id: EaterId) -> NutritionGoal | None:
        data = await self.table.get(eater_id, "GOAL")
        return None if data is None else goal_from_dict(data)


class DynamoDBWeightRepository:
    def __init__(self, table_name: str):
        self.table = _Table(table_name)

    async def save(self, record: WeightRecord) -> None:
        await self.table.put(record.eater_id, f"WEIGHT#{record.day.isoformat()}", {"kg": record.kg})

    async def find(self, eater_id: EaterId, start: date, end: date) -> list[WeightRecord]:
        from boto3.dynamodb.conditions import Key

        condition = Key("pk").eq(_pk(eater_id)) & Key("sk").between(
            f"WEIGHT#{start.isoformat()}", f"WEIGHT#{end.isoformat()}")
        # data に日付を入れていないので、sk から読む
        items = await self.table.query_items(KeyConditionExpression=condition)
        return [WeightRecord(eater_id, date.fromisoformat(item["sk"].removeprefix("WEIGHT#")),
                             json.loads(item["data"])["kg"]) for item in items]


class DynamoDBDayTypeRepository:
    def __init__(self, table_name: str):
        self.table = _Table(table_name)

    async def set(self, eater_id: EaterId, day: date, day_type: DayType) -> None:
        await self.table.put(eater_id, f"DAYTYPE#{day.isoformat()}", {"day_type": day_type.value})

    async def get(self, eater_id: EaterId, day: date) -> DayType | None:
        data = await self.table.get(eater_id, f"DAYTYPE#{day.isoformat()}")
        return None if data is None else DayType(data["day_type"])
