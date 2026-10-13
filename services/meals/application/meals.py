from datetime import date

from application.commands import IdFactory, MealChanges, NewMeal, new_id
from domain.errors import NotFound
from domain.meal import Meal
from domain.ports import EaterResolver, MealRepository
from domain.values import EatenOn, EaterId, MealSlot


class MealService:
    """食事の記録・読み取り・修正・削除・複製。本人は検証済みのアクセストークンの sub で受け取る。"""

    def __init__(self, eaters: EaterResolver, meals: MealRepository, ids: IdFactory = new_id):
        self.eaters, self.meals, self.ids = eaters, meals, ids

    async def record(self, subject: str, new: NewMeal) -> Meal:
        return (await self.record_many(subject, [new]))[0]

    async def record_many(self, subject: str, news: list[NewMeal]) -> list[Meal]:
        """写真をまとめて貼ったとき。全件を作れてから保存する（途中で1件が不正なら何も保存しない）。"""
        eater = await self.eaters.resolve(subject)
        meals = [self._create(eater, new) for new in news]
        for meal in meals:
            await self.meals.save(meal)
        return meals

    async def get(self, subject: str, meal_id: str) -> Meal:
        return await self._get(await self.eaters.resolve(subject), meal_id)

    async def list(self, subject: str, start: date, end: date, slot: MealSlot | None = None) -> list[Meal]:
        return await self.meals.find(await self.eaters.resolve(subject), start, end, slot)

    async def update(self, subject: str, meal_id: str, changes: MealChanges) -> Meal:
        meal = await self._get(await self.eaters.resolve(subject), meal_id)
        for item_id, amount in changes.amounts.items():
            meal = meal.change_amount(item_id, amount)
        for new_item in changes.add:
            meal = meal.add_item(new_item.to_item(self.ids))
        for item_id in changes.remove:
            meal = meal.remove_item(item_id)
        if changes.eaten_on:
            meal = meal.move_to(changes.eaten_on)
        await self.meals.save(meal)
        return meal

    async def delete(self, subject: str, meal_id: str) -> None:
        eater = await self.eaters.resolve(subject)
        await self._get(eater, meal_id)  # ほかの人の食事やない食事は消せない
        await self.meals.delete(eater, meal_id)

    async def copy(self, subject: str, meal_id: str, eaten_on: EatenOn) -> Meal:
        """昨日と同じ。"""
        original = await self._get(await self.eaters.resolve(subject), meal_id)
        copy = original.copy_to(self.ids(), eaten_on)
        await self.meals.save(copy)
        return copy

    def _create(self, eater: EaterId, new: NewMeal) -> Meal:
        items = tuple(item.to_item(self.ids) for item in new.items)
        return Meal(self.ids(), eater, new.eaten_on, items, new.description, new.source)

    async def _get(self, eater: EaterId, meal_id: str) -> Meal:
        meal = await self.meals.get(eater, meal_id)
        if meal is None:
            raise NotFound(f"食事 {meal_id} は見つかりません")
        return meal
