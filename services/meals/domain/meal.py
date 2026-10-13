from dataclasses import dataclass, replace

from domain.errors import MealError, NotFound
from domain.values import Confidence, EatenOn, EaterId, Nutrition, Quantity, Source


@dataclass(frozen=True)
class FoodItem:
    """品目（Meal の中のエンティティ）。「白米 200g」などの1行。

    nutrition はこの量のときの栄養。id は食事の中で行を指すために使う。
    """

    id: str
    name: str
    quantity: Quantity
    nutrition: Nutrition
    confidence: Confidence = Confidence.MEDIUM

    def __post_init__(self):
        if not self.name.strip():
            raise MealError("品目の名前が空です")

    def with_amount(self, amount: float) -> "FoodItem":
        """量を変える。単位はそのまま（200g → 1杯 は割合が計算できないため）。栄養も同じ割合で変わる。"""
        quantity = Quantity(amount, self.quantity.unit)
        return replace(self, quantity=quantity, nutrition=self.nutrition.times(amount / self.quantity.amount))


@dataclass(frozen=True)
class Meal:
    """集約：1回の食事。記録した時点で確定し、状態は持たない。品目は Meal を通してだけ変える。"""

    id: str
    eater_id: EaterId
    eaten_on: EatenOn
    items: tuple[FoodItem, ...]
    description: str  # 写真や言葉から Claude が読み取った説明。画像は保存しない
    source: Source

    def __post_init__(self):
        if not self.items:
            raise MealError("品目が1つもありません")
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise MealError("品目の id が重複しています")

    def total(self) -> Nutrition:
        return sum((item.nutrition for item in self.items), Nutrition.zero())

    def change_amount(self, item_id: str, amount: float) -> "Meal":
        item = self._item(item_id)
        return self._with_items(tuple(i.with_amount(amount) if i is item else i for i in self.items))

    def add_item(self, item: FoodItem) -> "Meal":
        return self._with_items(self.items + (item,))

    def remove_item(self, item_id: str) -> "Meal":
        item = self._item(item_id)
        if len(self.items) == 1:
            raise MealError("最後の品目は消せません。食事ごと消してください")
        return self._with_items(tuple(i for i in self.items if i is not item))

    def move_to(self, eaten_on: EatenOn) -> "Meal":
        return replace(self, eaten_on=eaten_on)

    def copy_to(self, new_id: str, eaten_on: EatenOn) -> "Meal":
        """昨日と同じ。別の食事として記録する。"""
        return replace(self, id=new_id, eaten_on=eaten_on, source=Source.COPY)

    def _item(self, item_id: str) -> FoodItem:
        for item in self.items:
            if item.id == item_id:
                return item
        raise NotFound(f"品目 {item_id} はこの食事にありません")

    def _with_items(self, items: tuple[FoodItem, ...]) -> "Meal":
        return replace(self, items=items)
