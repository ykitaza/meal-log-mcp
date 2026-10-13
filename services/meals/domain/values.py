"""値オブジェクト。どれも変更できず、作るときに決まりを確かめる。"""

from dataclasses import dataclass
from datetime import date, time
from enum import Enum

from domain.errors import MealError


@dataclass(frozen=True)
class EaterId:
    """食べた人。記録の持ち主。

    認可コンテキストの本人（sub）とは別の言葉なので、変換は腐敗防止層（EaterResolver）で行う。
    """

    value: str


@dataclass(frozen=True)
class Nutrition:
    """栄養。kcal と PFC（たんぱく質・脂質・炭水化物、g）。どれも0以上。"""

    kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float

    def __post_init__(self):
        if min(self.kcal, self.protein_g, self.fat_g, self.carbs_g) < 0:
            raise MealError("栄養の値は0以上である必要があります")

    @classmethod
    def zero(cls) -> "Nutrition":
        return cls(0, 0, 0, 0)

    def __add__(self, other: "Nutrition") -> "Nutrition":
        return Nutrition(
            self.kcal + other.kcal,
            self.protein_g + other.protein_g,
            self.fat_g + other.fat_g,
            self.carbs_g + other.carbs_g,
        )

    def times(self, factor: float) -> "Nutrition":
        return Nutrition(self.kcal * factor, self.protein_g * factor, self.fat_g * factor, self.carbs_g * factor)

    def minus(self, other: "Nutrition") -> "NutritionGap":
        """目標との差など。負になりうるので Nutrition ではなく NutritionGap で返す。"""
        return NutritionGap(
            self.kcal - other.kcal,
            self.protein_g - other.protein_g,
            self.fat_g - other.fat_g,
            self.carbs_g - other.carbs_g,
        )


@dataclass(frozen=True)
class NutritionGap:
    """栄養の差（残り、目標との差）。負の値もとる。目標がない項目は None。"""

    kcal: float | None
    protein_g: float | None
    fat_g: float | None
    carbs_g: float | None


class Unit(Enum):
    GRAM = "g"
    MILLILITER = "ml"
    PIECE = "個"
    CUP = "杯"


@dataclass(frozen=True)
class Quantity:
    """量。数と単位。"""

    amount: float
    unit: Unit

    def __post_init__(self):
        if self.amount <= 0:
            raise MealError("量は0より大きい必要があります")


class Confidence(Enum):
    """推定の確かさ。写真から推定したものは低いことが多い。"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MealSlot(Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"

    @classmethod
    def from_time(cls, at: time) -> "MealSlot":
        """時刻から区分を決める。境目は仮のもの。"""
        if 5 <= at.hour < 10:
            return cls.BREAKFAST
        if 10 <= at.hour < 15:
            return cls.LUNCH
        if 17 <= at.hour < 22:
            return cls.DINNER
        return cls.SNACK


@dataclass(frozen=True)
class EatenOn:
    """食べたとき。日付と区分は必須、時刻は分かれば持つ（写真の撮影日時は Claude に渡らないため）。"""

    day: date
    slot: MealSlot
    at: time | None = None

    @classmethod
    def from_time(cls, day: date, at: time) -> "EatenOn":
        return cls(day, MealSlot.from_time(at), at)


class Source(Enum):
    """記録の仕方。"""

    PHOTO = "photo"  # 写真から Claude が推定した
    TEXT = "text"  # 言葉から推定した
    NUMBERS = "numbers"  # kcal・PFC の数値だけ
    COPY = "copy"  # ほかの食事の複製（昨日と同じ）
    TEMPLATE = "template"  # いつもの


class DayType(Enum):
    TRAINING = "training"  # 筋トレの日
    REST = "rest"  # 休みの日
