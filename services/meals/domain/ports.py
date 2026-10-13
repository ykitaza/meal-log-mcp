"""ポート：食事記録のドメインが外に求める働きの型。実装は infrastructure/ に置く。

どれも食べた人（EaterId）ごとに分けて読み書きする。ほかの人の記録には届かない。
どれも外のシステム（DB など）を呼ぶ（待ち時間がある）ので、async にしておく。
"""

from datetime import date
from typing import Protocol

from domain.body_weight import WeightRecord
from domain.meal import Meal
from domain.meal_template import MealTemplate
from domain.nutrition_goal import NutritionGoal
from domain.values import DayType, EaterId, MealSlot


class EaterResolver(Protocol):
    async def resolve(self, subject: str) -> EaterId:
        """認可コンテキストの本人（アクセストークンの sub）を、食べた人に変える（腐敗防止層）。"""
        ...


class MealRepository(Protocol):
    async def save(self, meal: Meal) -> None: ...

    async def get(self, eater_id: EaterId, meal_id: str) -> Meal | None: ...

    async def delete(self, eater_id: EaterId, meal_id: str) -> None: ...

    async def find(self, eater_id: EaterId, start: date, end: date, slot: MealSlot | None = None) -> list[Meal]:
        """start から end まで（両端を含む）の食事を、食べた日・区分の順で返す。"""
        ...


class MealTemplateRepository(Protocol):
    async def save(self, template: MealTemplate) -> None:
        """同じ名前があれば上書きする。"""
        ...

    async def get(self, eater_id: EaterId, name: str) -> MealTemplate | None: ...

    async def list(self, eater_id: EaterId) -> list[MealTemplate]: ...


class GoalRepository(Protocol):
    async def save(self, goal: NutritionGoal) -> None: ...

    async def get(self, eater_id: EaterId) -> NutritionGoal | None: ...


class WeightRepository(Protocol):
    async def save(self, record: WeightRecord) -> None:
        """同じ日の記録があれば上書きする。"""
        ...

    async def find(self, eater_id: EaterId, start: date, end: date) -> list[WeightRecord]:
        """start から end まで（両端を含む）の記録を、日付の順で返す。"""
        ...


class DayTypeRepository(Protocol):
    async def set(self, eater_id: EaterId, day: date, day_type: DayType) -> None: ...

    async def get(self, eater_id: EaterId, day: date) -> DayType | None:
        """決めていない日は None。"""
        ...
