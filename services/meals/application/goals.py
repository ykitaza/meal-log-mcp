from dataclasses import replace
from datetime import date

from domain.goal_suggestion import BodyProfile, GoalPlan, GoalSuggestion, suggest_goal
from domain.nutrition_goal import NutritionGoal
from domain.ports import DayTypeRepository, EaterResolver, GoalRepository
from domain.values import DayType


class GoalService:
    """目標と日の種類。どちらも食べた人ごとに決める。"""

    def __init__(self, eaters: EaterResolver, goals: GoalRepository, day_types: DayTypeRepository):
        self.eaters, self.goals, self.day_types = eaters, goals, day_types

    async def suggest(self, subject: str, profile: BodyProfile, plan: GoalPlan) -> GoalSuggestion:
        """目標の案を計算する。保存はしない（本人が案を見て決めてから set_goals で保存する）。"""
        return suggest_goal(await self.eaters.resolve(subject), profile, plan)

    async def current(self, subject: str) -> NutritionGoal | None:
        return await self.goals.get(await self.eaters.resolve(subject))

    async def set_goals(self, subject: str, goal: NutritionGoal) -> NutritionGoal:
        """goal の eater_id は無視し、トークンの本人のものとして保存する。"""
        goal = replace(goal, eater_id=await self.eaters.resolve(subject))
        await self.goals.save(goal)
        return goal

    async def set_day_type(self, subject: str, day: date, day_type: DayType) -> None:
        await self.day_types.set(await self.eaters.resolve(subject), day, day_type)
