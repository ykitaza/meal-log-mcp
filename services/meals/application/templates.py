from application.commands import IdFactory, new_id
from domain.errors import NotFound
from domain.meal import Meal
from domain.meal_template import MealTemplate
from domain.ports import EaterResolver, MealRepository, MealTemplateRepository
from domain.values import EatenOn


class TemplateService:
    """いつもの。記録済みの食事に名前を付けて保存し、名前で記録する。"""

    def __init__(
        self,
        eaters: EaterResolver,
        meals: MealRepository,
        templates: MealTemplateRepository,
        ids: IdFactory = new_id,
    ):
        self.eaters, self.meals, self.templates, self.ids = eaters, meals, templates, ids

    async def save(self, subject: str, meal_id: str, name: str) -> MealTemplate:
        meal = await self.meals.get(await self.eaters.resolve(subject), meal_id)
        if meal is None:
            raise NotFound(f"食事 {meal_id} は見つかりません")
        template = MealTemplate.from_meal(meal, name)
        await self.templates.save(template)
        return template

    async def record(self, subject: str, name: str, eaten_on: EatenOn) -> Meal:
        eater = await self.eaters.resolve(subject)
        template = await self.templates.get(eater, name)
        if template is None:
            names = "、".join(t.name for t in await self.templates.list(eater)) or "なし"
            raise NotFound(f"いつもの「{name}」は見つかりません（保存してあるもの：{names}）")
        meal = template.to_meal(self.ids(), eaten_on)
        await self.meals.save(meal)
        return meal
