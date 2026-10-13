from datetime import date, timedelta

from domain.body_weight import GoalProgress, WeightRecord
from domain.ports import EaterResolver, GoalRepository, WeightRepository

PROGRESS_DAYS = 90  # 道のりの画面に出す期間


class WeightService:
    """体重の記録と、ゴールまでの道のり。"""

    def __init__(self, eaters: EaterResolver, weights: WeightRepository, goals: GoalRepository):
        self.eaters, self.weights, self.goals = eaters, weights, goals

    async def record(self, subject: str, day: date, kg: float) -> WeightRecord:
        record = WeightRecord(await self.eaters.resolve(subject), day, kg)
        await self.weights.save(record)
        return record

    async def progress(self, subject: str, today: date) -> GoalProgress:
        eater = await self.eaters.resolve(subject)
        records = await self.weights.find(eater, today - timedelta(days=PROGRESS_DAYS), today)
        return GoalProgress(await self.goals.get(eater), tuple(records), today)
