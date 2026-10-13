from datetime import date, timedelta

from domain.ports import DayTypeRepository, EaterResolver, GoalRepository, MealRepository
from domain.summary import DailySummary, WeeklyReview
from domain.values import DayType, EaterId

# 日の種類を決めていない日は休みの日として計算する（利用者に聞かない。筋トレの日だけ本人が言う）
DEFAULT_DAY_TYPE = DayType.REST


class SummaryService:
    """今日の合計と残り、週のふり返り。保存せず、その都度計算する。"""

    def __init__(
        self,
        eaters: EaterResolver,
        meals: MealRepository,
        goals: GoalRepository,
        day_types: DayTypeRepository,
    ):
        self.eaters, self.meals, self.goals, self.day_types = eaters, meals, goals, day_types

    async def daily(self, subject: str, day: date) -> DailySummary:
        return await self._daily(await self.eaters.resolve(subject), day)

    async def weekly(self, subject: str, last_day: date) -> WeeklyReview:
        """last_day までの7日間。"""
        eater = await self.eaters.resolve(subject)
        return WeeklyReview(tuple([await self._daily(eater, last_day - timedelta(days=n)) for n in range(6, -1, -1)]))

    async def _daily(self, eater: EaterId, day: date) -> DailySummary:
        day_type = await self.day_types.get(eater, day) or DEFAULT_DAY_TYPE
        meals = tuple(await self.meals.find(eater, day, day))
        return DailySummary(day, day_type, meals, await self.goals.get(eater))
