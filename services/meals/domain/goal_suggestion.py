"""目標の案。本人が答えた体のデータから、決まった式で計算する（Claude に数字を考えさせないため）。

必須なのは方針だけ。答えたくない項目は空でよく、分かっている項目だけで出せる目標を出す。
- たんぱく質：体重が分かれば、体重 × protein_per_kg
- kcal・脂質・炭水化物：体重・身長・年齢・普段の活動量が分かれば計算する
  - 基礎代謝：Mifflin-St Jeor の式。性別で定数だけが変わる（男性 +5、女性 −161、答えないときは中間の −78）
  - 休みの日の消費：基礎代謝 × 普段の活動量の係数
  - 筋トレの日の消費：休みの日 ＋ 筋トレの分（筋トレの METs を 5 とし、安静の 1 を引いた分 × 体重 × 時間）。
    筋トレの時間が分からなければ、休みの日と同じにする
  - 増量・減量：体重 1kg ≒ 7,700kcal として、1週間のペースを1日あたりに直して足し引きする
  - 脂質：kcal の 25%。炭水化物：残り
"""

from dataclasses import dataclass
from enum import Enum

from domain.errors import MealError
from domain.nutrition_goal import DailyTarget, EatingStyle, NutritionGoal, Policy
from domain.values import EaterId

KCAL_PER_KG_BODY_WEIGHT = 7700
TRAINING_METS = 5.0
FAT_RATIO = 0.25


class Sex(Enum):
    MALE = "male"
    FEMALE = "female"
    UNSPECIFIED = "unspecified"  # 答えない

    @property
    def bmr_constant(self) -> float:
        return {"male": 5, "female": -161, "unspecified": -78}[self.value]


class DailyActivity(Enum):
    """筋トレ以外の普段の活動量。係数は基礎代謝に掛ける。"""

    LOW = "low"  # 座り仕事が中心
    MODERATE = "moderate"  # 立ち仕事や通勤の歩きが多い
    HIGH = "high"  # 体を動かす仕事

    @property
    def factor(self) -> float:
        return {"low": 1.2, "moderate": 1.375, "high": 1.55}[self.value]


@dataclass(frozen=True)
class BodyProfile:
    """本人の体のデータ。どれも任意（答えたくない項目は None）。推測で埋めない。"""

    sex: Sex = Sex.UNSPECIFIED
    age: int | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    daily_activity: DailyActivity | None = None
    training_minutes: int | None = None  # 筋トレ1回あたりの時間

    def __post_init__(self):
        checks = [
            (self.age, 15, 100, "年齢は15〜100で入力してください"),
            (self.height_cm, 100, 250, "身長は100〜250cmで入力してください"),
            (self.weight_kg, 30, 300, "体重は30〜300kgで入力してください"),
            (self.training_minutes, 0, 300, "筋トレの時間は0〜300分で入力してください"),
        ]
        for value, low, high, message in checks:
            if value is not None and not low <= value <= high:
                raise MealError(message)

    def basal_metabolism(self) -> float | None:
        if None in (self.weight_kg, self.height_cm, self.age):
            return None
        return 10 * self.weight_kg + 6.25 * self.height_cm - 5 * self.age + self.sex.bmr_constant

    def rest_day_expenditure(self) -> float | None:
        bmr = self.basal_metabolism()
        if bmr is None or self.daily_activity is None:
            return None
        return bmr * self.daily_activity.factor

    def training_expenditure(self) -> float:
        """筋トレ1回で増える消費。体重か時間が分からなければ 0。"""
        if self.weight_kg is None or self.training_minutes is None:
            return 0
        return (TRAINING_METS - 1) * self.weight_kg * self.training_minutes / 60


@dataclass(frozen=True)
class GoalPlan:
    """どう変えたいか。"""

    policy: Policy
    pace_kg_per_week: float = 0  # 増量・減量のペース。維持なら 0
    protein_per_kg: float = 2.0
    eating_style: EatingStyle | None = None
    target_weight_kg: float | None = None

    def __post_init__(self):
        if self.policy == Policy.MAINTAIN and self.pace_kg_per_week != 0:
            raise MealError("維持のときはペースを 0 にしてください")
        if self.policy != Policy.MAINTAIN and not 0 < self.pace_kg_per_week <= 1:
            raise MealError("ペースは1週間あたり 0〜1kg で入力してください")
        if not 1.0 <= self.protein_per_kg <= 3.0:
            raise MealError("体重1kgあたりのたんぱく質は 1.0〜3.0g で入力してください")

    def daily_adjustment(self) -> float:
        """1日あたりに足す（減量なら引く）kcal。"""
        sign = {Policy.BULK: 1, Policy.CUT: -1, Policy.MAINTAIN: 0}[self.policy]
        return sign * self.pace_kg_per_week * KCAL_PER_KG_BODY_WEIGHT / 7


@dataclass(frozen=True)
class GoalSuggestion:
    goal: NutritionGoal
    notes: tuple[str, ...]  # 何が分からなかったので、どの目標を出していないか


def suggest_goal(eater_id: EaterId, profile: BodyProfile, plan: GoalPlan) -> GoalSuggestion:
    notes = []
    protein_g = None
    if profile.weight_kg is None:
        notes.append("体重が分からないので、たんぱく質と kcal の目標は出していません")
    else:
        protein_g = profile.weight_kg * plan.protein_per_kg

    rest = profile.rest_day_expenditure()
    training_day = rest_day = None
    if rest is None:
        if profile.weight_kg is not None:
            notes.append("身長・年齢・普段の活動量のどれかが分からないので、kcal・脂質・炭水化物の目標は出していません")
    else:
        def target(expenditure: float) -> DailyTarget:
            kcal = round(expenditure + plan.daily_adjustment(), -1)  # 10kcal 単位に丸める
            fat_g = round(kcal * FAT_RATIO / 9)
            carbs_g = round(max(kcal - protein_g * 4 - fat_g * 9, 0) / 4)
            return DailyTarget(kcal, fat_g, carbs_g)

        training_day, rest_day = target(rest + profile.training_expenditure()), target(rest)
        if profile.sex == Sex.UNSPECIFIED:
            notes.append("性別を使わずに計算した目安です")
        if profile.training_minutes is None:
            notes.append("筋トレの時間が分からないので、筋トレの日も休みの日と同じ目標にしています")

    goal = NutritionGoal(
        eater_id=eater_id,
        policy=plan.policy,
        body_weight_kg=profile.weight_kg,
        protein_per_kg=plan.protein_per_kg if profile.weight_kg is not None else None,
        training_day=training_day,
        rest_day=rest_day,
        eating_style=plan.eating_style,
        target_weight_kg=plan.target_weight_kg,
    )
    return GoalSuggestion(goal, tuple(notes))
