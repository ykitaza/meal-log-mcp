"""まとめ。保存せず、記録から計算して出す（集約ではない）。"""

from dataclasses import dataclass
from datetime import date

from domain.meal import Meal
from domain.nutrition_goal import NutritionGoal, Target
from domain.values import DayType, Nutrition, NutritionGap


@dataclass(frozen=True)
class DailySummary:
    """1日のまとめ。目標が未設定なら target と remaining は None。目標がない項目の残りも None。"""

    day: date
    day_type: DayType
    meals: tuple[Meal, ...]
    goal: NutritionGoal | None

    @property
    def total(self) -> Nutrition:
        return sum((meal.total() for meal in self.meals), Nutrition.zero())

    @property
    def target(self) -> Target | None:
        return self.goal.target_for(self.day_type) if self.goal else None

    @property
    def remaining(self) -> NutritionGap | None:
        return self.target.remaining(self.total) if self.target else None


@dataclass(frozen=True)
class WeeklyReview:
    """週のふり返り。平均は記録した日だけで出す。記録しなかった日を責めない。"""

    days: tuple[DailySummary, ...]  # 期間のすべての日（記録がない日も含む）

    @property
    def recorded_days(self) -> tuple[DailySummary, ...]:
        return tuple(day for day in self.days if day.meals)

    @property
    def average(self) -> Nutrition | None:
        totals = [day.total for day in self.recorded_days]
        return sum(totals, Nutrition.zero()).times(1 / len(totals)) if totals else None

    @property
    def average_target(self) -> Target | None:
        """記録した日の目標の平均（筋トレの日と休みの日で目標が違うため）。項目ごとに、全日に目標があるときだけ出す。"""
        targets = [day.target for day in self.recorded_days]
        if not targets or None in targets:
            return None
        columns = zip(*(t.values() for t in targets))
        return Target(*(None if None in col else sum(col) / len(col) for col in columns))

    @property
    def gap(self) -> NutritionGap | None:
        """平均から目標を引いた差。正なら目標より多く、負なら少ない。目標がない項目は None。"""
        if self.average is None or self.average_target is None:
            return None
        remaining = self.average_target.remaining(self.average)
        return NutritionGap(*(None if r is None else -r for r in
                              (remaining.kcal, remaining.protein_g, remaining.fat_g, remaining.carbs_g)))
