"""ツールの入力の型。SDK がここから JSON Schema を作り、Claude に見せる。ドメインの型への変換もここで行う。"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from application.commands import NewItem, NewMeal
from domain.values import Confidence, EatenOn, MealSlot, Nutrition, Quantity, Source, Unit

SlotName = Literal["breakfast", "lunch", "dinner", "snack"]


class ItemInput(BaseModel):
    name: str = Field(description="品目の名前。例：白米、鶏むね肉の照り焼き")
    amount: float = Field(gt=0, description="量の数")
    unit: Literal["g", "ml", "個", "杯"]
    kcal: float = Field(ge=0, description="この量でのエネルギー")
    protein_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    confidence: Literal["high", "medium", "low"] = Field(
        "medium", description="推定の確かさ。写真から量を推定したものは low か medium")

    def to_command(self) -> NewItem:
        return NewItem(
            self.name,
            Quantity(self.amount, Unit(self.unit)),
            Nutrition(self.kcal, self.protein_g, self.fat_g, self.carbs_g),
            Confidence(self.confidence),
        )


class WhenInput(BaseModel):
    date: dt.date = Field(description="食べた日（YYYY-MM-DD）")
    slot: SlotName = Field(description="朝食・昼食・夕食・間食。利用者の指示、時刻、料理の内容の順で決める")
    time: dt.time | None = Field(None, description="食べた時刻（HH:MM）。分からなければ省く")

    def to_eaten_on(self) -> EatenOn:
        return EatenOn(self.date, MealSlot(self.slot), self.time)


class MealInput(WhenInput):
    items: list[ItemInput] = Field(min_length=1)
    description: str = Field(description="写真や言葉から読み取った食事の説明。画像は保存しないので、ここに残す")
    source: Literal["photo", "text", "numbers"] = Field(description="写真から／言葉から／kcal・PFC の数値だけ")

    def to_command(self) -> NewMeal:
        return NewMeal(
            self.to_eaten_on(), tuple(i.to_command() for i in self.items), self.description, Source(self.source))


class AmountChange(BaseModel):
    item_id: str
    amount: float = Field(gt=0, description="新しい量の数。単位は記録したときのまま")


class DailyTargetInput(BaseModel):
    kcal: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
