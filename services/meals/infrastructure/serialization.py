"""集約を保存できる形（dict）に変換する。リポジトリの実装だけが使う。"""

from datetime import date, time

from domain.meal import FoodItem, Meal
from domain.meal_template import MealTemplate
from domain.nutrition_goal import DailyTarget, EatingStyle, NutritionGoal, Policy
from domain.values import Confidence, EatenOn, EaterId, MealSlot, Nutrition, Quantity, Source, Unit


def _nutrition_to_dict(n: Nutrition) -> dict:
    return {"kcal": n.kcal, "protein_g": n.protein_g, "fat_g": n.fat_g, "carbs_g": n.carbs_g}


def _item_to_dict(i: FoodItem) -> dict:
    return {
        "id": i.id,
        "name": i.name,
        "quantity": {"amount": i.quantity.amount, "unit": i.quantity.unit.value},
        "nutrition": _nutrition_to_dict(i.nutrition),
        "confidence": i.confidence.value,
    }


def _item_from_dict(d: dict) -> FoodItem:
    return FoodItem(
        id=d["id"],
        name=d["name"],
        quantity=Quantity(d["quantity"]["amount"], Unit(d["quantity"]["unit"])),
        nutrition=Nutrition(**d["nutrition"]),
        confidence=Confidence(d["confidence"]),
    )


def meal_to_dict(m: Meal) -> dict:
    return {
        "id": m.id,
        "eater_id": m.eater_id.value,
        "day": m.eaten_on.day.isoformat(),
        "slot": m.eaten_on.slot.value,
        "at": m.eaten_on.at.isoformat() if m.eaten_on.at else None,
        "items": [_item_to_dict(i) for i in m.items],
        "description": m.description,
        "source": m.source.value,
    }


def meal_from_dict(d: dict) -> Meal:
    eaten_on = EatenOn(
        date.fromisoformat(d["day"]), MealSlot(d["slot"]), time.fromisoformat(d["at"]) if d["at"] else None)
    return Meal(
        id=d["id"],
        eater_id=EaterId(d["eater_id"]),
        eaten_on=eaten_on,
        items=tuple(_item_from_dict(i) for i in d["items"]),
        description=d["description"],
        source=Source(d["source"]),
    )


def template_to_dict(t: MealTemplate) -> dict:
    return {"eater_id": t.eater_id.value, "name": t.name, "items": [_item_to_dict(i) for i in t.items]}


def template_from_dict(d: dict) -> MealTemplate:
    return MealTemplate(EaterId(d["eater_id"]), d["name"], tuple(_item_from_dict(i) for i in d["items"]))


def _target_to_dict(t: DailyTarget) -> dict:
    return {"kcal": t.kcal, "fat_g": t.fat_g, "carbs_g": t.carbs_g}


def goal_to_dict(g: NutritionGoal) -> dict:
    return {
        "eater_id": g.eater_id.value,
        "policy": g.policy.value,
        "body_weight_kg": g.body_weight_kg,
        "protein_per_kg": g.protein_per_kg,
        "training_day": _target_to_dict(g.training_day) if g.training_day else None,
        "rest_day": _target_to_dict(g.rest_day) if g.rest_day else None,
        "eating_style": g.eating_style.value if g.eating_style else None,
        "target_weight_kg": g.target_weight_kg,
    }


def goal_from_dict(d: dict) -> NutritionGoal:
    return NutritionGoal(
        eater_id=EaterId(d["eater_id"]),
        policy=Policy(d["policy"]),
        body_weight_kg=d["body_weight_kg"],
        protein_per_kg=d["protein_per_kg"],
        training_day=DailyTarget(**d["training_day"]) if d["training_day"] else None,
        rest_day=DailyTarget(**d["rest_day"]) if d["rest_day"] else None,
        eating_style=EatingStyle(d["eating_style"]) if d["eating_style"] else None,
        target_weight_kg=d.get("target_weight_kg"),  # 足す前に保存した目標には無い
    )
