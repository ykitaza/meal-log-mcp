from dataclasses import dataclass
from enum import Enum

from domain.errors import MealError
from domain.values import DayType, EaterId, Nutrition, NutritionGap


class Policy(Enum):
    BULK = "bulk"  # 増量
    CUT = "cut"  # 減量
    MAINTAIN = "maintain"  # 維持


class EatingStyle(Enum):
    """自炊・外食・コンビニのどれが多いか。次の食事の候補を出すときに使う。"""

    HOME_COOKED = "home_cooked"
    EATING_OUT = "eating_out"
    CONVENIENCE_STORE = "convenience_store"


@dataclass(frozen=True)
class DailyTarget:
    """1日の目標のうち、日の種類で変わるもの。たんぱく質は体重から決めるのでここには持たない。"""

    kcal: float
    fat_g: float
    carbs_g: float

    def __post_init__(self):
        if min(self.kcal, self.fat_g, self.carbs_g) < 0:
            raise MealError("目標の値は0以上である必要があります")


@dataclass(frozen=True)
class Target:
    """1日の目標。分かっている項目だけ持つ（None はその項目の目標がない）。"""

    kcal: float | None = None
    protein_g: float | None = None
    fat_g: float | None = None
    carbs_g: float | None = None

    def values(self) -> tuple[float | None, ...]:
        return (self.kcal, self.protein_g, self.fat_g, self.carbs_g)

    def remaining(self, eaten: Nutrition) -> NutritionGap:
        """目標から、食べた分を引いた残り。"""
        eaten_values = (eaten.kcal, eaten.protein_g, eaten.fat_g, eaten.carbs_g)
        return NutritionGap(*(None if t is None else t - e for t, e in zip(self.values(), eaten_values)))


@dataclass(frozen=True)
class NutritionGoal:
    """集約：目標。食べた人ごとに1つ。アプリに決め打ちせず、本人が決める。

    必須なのは方針だけ。体重や1日の目標は、本人が答えた分だけ持つ（答えたくない項目があってよい）。
    """

    eater_id: EaterId
    policy: Policy
    body_weight_kg: float | None = None
    protein_per_kg: float | None = None  # 体重1kgあたりのたんぱく質（g）。筋トレをしているなら 1.6〜2.2 がよく使われる
    training_day: DailyTarget | None = None
    rest_day: DailyTarget | None = None
    eating_style: EatingStyle | None = None
    target_weight_kg: float | None = None  # 目標体重（ゴールまでの道のりに使う）

    def __post_init__(self):
        if self.target_weight_kg is not None and not 30 <= self.target_weight_kg <= 300:
            raise MealError("目標体重は30〜300kgで入力してください")
        if self.body_weight_kg is not None and self.body_weight_kg <= 0:
            raise MealError("体重は0より大きい必要があります")
        if self.protein_per_kg is not None and self.protein_per_kg <= 0:
            raise MealError("体重1kgあたりのたんぱく質は0より大きい必要があります")
        if (self.training_day is None) != (self.rest_day is None):
            raise MealError("筋トレの日と休みの日の目標は、両方決めるか、両方決めないかにしてください")

    def target_for(self, day_type: DayType) -> Target:
        daily = self.training_day if day_type == DayType.TRAINING else self.rest_day
        protein = None  # 日の種類によらず同じ。体重が分からなければ目標なし
        if self.body_weight_kg is not None and self.protein_per_kg is not None:
            protein = self.body_weight_kg * self.protein_per_kg
        if daily is None:
            return Target(protein_g=protein)
        return Target(daily.kcal, protein, daily.fat_g, daily.carbs_g)
