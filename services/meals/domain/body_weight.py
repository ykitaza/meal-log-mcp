from dataclasses import dataclass
from datetime import date, timedelta

from domain.errors import MealError
from domain.nutrition_goal import NutritionGoal, Policy
from domain.values import EaterId

TREND_WINDOW_DAYS = 28  # 1週間あたりの変化は、直近4週間の記録から出す


@dataclass(frozen=True)
class WeightRecord:
    """体重の記録。1日に1つ（同じ日にもう一度記録したら上書き）。"""

    eater_id: EaterId
    day: date
    kg: float

    def __post_init__(self):
        if not 30 <= self.kg <= 300:
            raise MealError("体重は30〜300kgで入力してください")


@dataclass(frozen=True)
class GoalProgress:
    """ゴールまでの道のり。保存せず、目標と体重の記録から計算する。"""

    goal: NutritionGoal | None
    records: tuple[WeightRecord, ...]  # 日付の順
    today: date

    @property
    def latest(self) -> WeightRecord | None:
        return self.records[-1] if self.records else None

    @property
    def target_kg(self) -> float | None:
        return self.goal.target_weight_kg if self.goal else None

    @property
    def remaining_kg(self) -> float | None:
        """目標体重まで、あと何kg（増やすなら正、減らすなら負）。"""
        if self.latest is None or self.target_kg is None:
            return None
        return self.target_kg - self.latest.kg

    @property
    def weekly_change_kg(self) -> float | None:
        """直近4週間の、1週間あたりの体重の変化。1週間以上の間をあけた記録が2つないと出せない。"""
        since = self.today - timedelta(days=TREND_WINDOW_DAYS)
        recent = [r for r in self.records if r.day >= since]
        if len(recent) < 2 or (recent[-1].day - recent[0].day).days < 7:
            return None
        return (recent[-1].kg - recent[0].kg) / ((recent[-1].day - recent[0].day).days / 7)

    @property
    def weeks_to_goal(self) -> float | None:
        """今のペースが続いたときに、目標体重まであと何週か。向きが逆か、変化がなければ出さない。"""
        remaining, change = self.remaining_kg, self.weekly_change_kg
        if remaining is None or not change or remaining / change <= 0:
            return None
        return remaining / change

    @property
    def on_track(self) -> bool | None:
        """方針の向きに体重が動いているか（維持なら、週 0.25kg 以内の変化か）。"""
        change = self.weekly_change_kg
        if change is None or self.goal is None:
            return None
        if self.goal.policy == Policy.MAINTAIN:
            return abs(change) <= 0.25
        return change > 0 if self.goal.policy == Policy.BULK else change < 0
