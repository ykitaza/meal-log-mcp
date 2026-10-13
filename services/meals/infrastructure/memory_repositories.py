"""メモリー上のリポジトリ。PC で動かすときとテストで使う。プロセスが終わると消える。"""

from datetime import date

from domain.body_weight import WeightRecord
from domain.meal import Meal
from domain.meal_template import MealTemplate
from domain.nutrition_goal import NutritionGoal
from domain.values import DayType, EaterId, MealSlot

SLOT_ORDER = list(MealSlot)


class InMemoryMealRepository:
    def __init__(self):
        self._meals: dict[tuple[EaterId, str], Meal] = {}

    async def save(self, meal: Meal) -> None:
        self._meals[(meal.eater_id, meal.id)] = meal

    async def get(self, eater_id: EaterId, meal_id: str) -> Meal | None:
        return self._meals.get((eater_id, meal_id))

    async def delete(self, eater_id: EaterId, meal_id: str) -> None:
        self._meals.pop((eater_id, meal_id), None)

    async def find(self, eater_id: EaterId, start: date, end: date, slot: MealSlot | None = None) -> list[Meal]:
        meals = [
            m for (owner, _), m in self._meals.items()
            if owner == eater_id and start <= m.eaten_on.day <= end and (slot is None or m.eaten_on.slot == slot)
        ]
        return sorted(meals, key=lambda m: (m.eaten_on.day, SLOT_ORDER.index(m.eaten_on.slot)))


class InMemoryMealTemplateRepository:
    def __init__(self):
        self._templates: dict[tuple[EaterId, str], MealTemplate] = {}

    async def save(self, template: MealTemplate) -> None:
        self._templates[(template.eater_id, template.name)] = template

    async def get(self, eater_id: EaterId, name: str) -> MealTemplate | None:
        return self._templates.get((eater_id, name))

    async def list(self, eater_id: EaterId) -> list[MealTemplate]:
        return [t for (owner, _), t in self._templates.items() if owner == eater_id]


class InMemoryGoalRepository:
    def __init__(self):
        self._goals: dict[EaterId, NutritionGoal] = {}

    async def save(self, goal: NutritionGoal) -> None:
        self._goals[goal.eater_id] = goal

    async def get(self, eater_id: EaterId) -> NutritionGoal | None:
        return self._goals.get(eater_id)


class InMemoryWeightRepository:
    def __init__(self):
        self._records: dict[tuple[EaterId, date], WeightRecord] = {}

    async def save(self, record: WeightRecord) -> None:
        self._records[(record.eater_id, record.day)] = record

    async def find(self, eater_id: EaterId, start: date, end: date) -> list[WeightRecord]:
        found = [r for (owner, day), r in self._records.items() if owner == eater_id and start <= day <= end]
        return sorted(found, key=lambda r: r.day)


class InMemoryDayTypeRepository:
    def __init__(self):
        self._day_types: dict[tuple[EaterId, date], DayType] = {}

    async def set(self, eater_id: EaterId, day: date, day_type: DayType) -> None:
        self._day_types[(eater_id, day)] = day_type

    async def get(self, eater_id: EaterId, day: date) -> DayType | None:
        return self._day_types.get((eater_id, day))
