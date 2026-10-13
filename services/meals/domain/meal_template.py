from dataclasses import dataclass

from domain.errors import MealError
from domain.meal import FoodItem, Meal
from domain.values import EatenOn, EaterId, Source


@dataclass(frozen=True)
class MealTemplate:
    """集約：いつもの。名前を付けて保存した品目の組み合わせ。名前は食べた人の中で一意。"""

    eater_id: EaterId
    name: str
    items: tuple[FoodItem, ...]

    def __post_init__(self):
        if not self.name.strip():
            raise MealError("いつものの名前が空です")
        if not self.items:
            raise MealError("品目が1つもありません")

    @classmethod
    def from_meal(cls, meal: Meal, name: str) -> "MealTemplate":
        return cls(meal.eater_id, name, meal.items)

    def to_meal(self, meal_id: str, eaten_on: EatenOn) -> Meal:
        return Meal(meal_id, self.eater_id, eaten_on, self.items, f"いつもの：{self.name}", Source.TEMPLATE)
