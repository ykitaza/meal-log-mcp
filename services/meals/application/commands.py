"""ユースケースへの入力。品目の id はサーバーが決めるので、入力には含めない。"""

from dataclasses import dataclass, field
from typing import Callable
from uuid import uuid4

from domain.meal import FoodItem
from domain.values import Confidence, EatenOn, Nutrition, Quantity, Source

IdFactory = Callable[[], str]


def new_id() -> str:
    return uuid4().hex[:12]


@dataclass(frozen=True)
class NewItem:
    name: str
    quantity: Quantity
    nutrition: Nutrition
    confidence: Confidence = Confidence.MEDIUM

    def to_item(self, ids: IdFactory) -> FoodItem:
        return FoodItem(ids(), self.name, self.quantity, self.nutrition, self.confidence)


@dataclass(frozen=True)
class NewMeal:
    eaten_on: EatenOn
    items: tuple[NewItem, ...]
    description: str
    source: Source


@dataclass(frozen=True)
class MealChanges:
    """update_meal で一度に送られる変更。適用する順は 量 → 追加 → 削除 → 日時。"""

    amounts: dict[str, float] = field(default_factory=dict)  # 品目の id → 新しい量（単位はそのまま）
    add: tuple[NewItem, ...] = ()
    remove: tuple[str, ...] = ()  # 品目の id
    eaten_on: EatenOn | None = None
