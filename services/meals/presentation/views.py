"""ツールの出力の形。数値は小数第1位で丸める（推定値なので、それ以上の桁は意味がない）。"""

from dataclasses import astuple

from domain.body_weight import GoalProgress
from domain.meal import Meal
from domain.meal_template import MealTemplate
from domain.nutrition_goal import NutritionGoal
from domain.summary import DailySummary, WeeklyReview
from domain.nutrition_goal import Target
from domain.values import DayType, Nutrition, NutritionGap

KEYS = ("kcal", "protein_g", "fat_g", "carbs_g")


def nutrition(n: Nutrition | NutritionGap | Target | None) -> dict | None:
    """目標がない項目は None のまま返す。"""
    return None if n is None else dict(zip(KEYS, (None if v is None else round(v, 1) for v in astuple(n))))


def meal(m: Meal) -> dict:
    return {
        "meal_id": m.id,
        "date": m.eaten_on.day.isoformat(),
        "slot": m.eaten_on.slot.value,
        "time": m.eaten_on.at.strftime("%H:%M") if m.eaten_on.at else None,
        "description": m.description,
        "source": m.source.value,
        "items": [
            {
                "item_id": i.id,
                "name": i.name,
                "amount": i.quantity.amount,
                "unit": i.quantity.unit.value,
                **nutrition(i.nutrition),
                "confidence": i.confidence.value,
            }
            for i in m.items
        ],
        "total": nutrition(m.total()),
    }


def template(t: MealTemplate) -> dict:
    return {"name": t.name, "items": [{"name": i.name, "amount": i.quantity.amount, "unit": i.quantity.unit.value}
                                      for i in t.items]}


def goal(g: NutritionGoal) -> dict:
    return {
        "policy": g.policy.value,
        "body_weight_kg": g.body_weight_kg,
        "protein_per_kg": g.protein_per_kg,
        "training_day": nutrition(g.target_for(DayType.TRAINING)),
        "rest_day": nutrition(g.target_for(DayType.REST)),
        "eating_style": g.eating_style.value if g.eating_style else None,
        "target_weight_kg": g.target_weight_kg,
    }


def daily(s: DailySummary) -> dict:
    view = {
        "date": s.day.isoformat(),
        "day_type": s.day_type.value,
        "meals": [{"meal_id": m.id, "slot": m.eaten_on.slot.value, "description": m.description,
                   "name": "、".join(i.name for i in m.items), "kcal": round(m.total().kcal, 1)} for m in s.meals],
        "total": nutrition(s.total),
        "goal": goal(s.goal) if s.goal else None,  # 方針だけの目標もある（そのときは target の数字が null）
        "target": nutrition(s.target),
        "remaining": nutrition(s.remaining),
    }
    if s.goal is None:
        view["note"] = "目標が未設定です。利用者に方針（増量・減量・維持）と体重などを聞いて set_goals を呼んでください"
    return view


def weekly(r: WeeklyReview) -> dict:
    return {
        "from": r.days[0].day.isoformat(),
        "to": r.days[-1].day.isoformat(),
        "goal": goal(r.days[-1].goal) if r.days[-1].goal else None,
        "recorded_days": len(r.recorded_days),
        "total_days": len(r.days),
        "average_of_recorded_days": nutrition(r.average),
        "average_target": nutrition(r.average_target),
        "gap": nutrition(r.gap),
        "days": [
            {
                "date": d.day.isoformat(),
                "day_type": d.day_type.value,
                "recorded": bool(d.meals),
                **nutrition(d.total),
                "target_kcal": d.target.kcal if d.target else None,
            }
            for d in r.days
        ],
    }


def progress(p: GoalProgress) -> dict:
    def kg(value: float | None, digits: int = 1) -> float | None:
        return None if value is None else round(value, digits)

    return {
        "policy": p.goal.policy.value if p.goal else None,
        "target_kg": p.target_kg,
        "latest": {"date": p.latest.day.isoformat(), "kg": p.latest.kg} if p.latest else None,
        "remaining_kg": kg(p.remaining_kg),
        "weekly_change_kg": kg(p.weekly_change_kg, 2),
        "weeks_to_goal": kg(p.weeks_to_goal),
        "on_track": p.on_track,
        "records": [{"date": r.day.isoformat(), "kg": r.kg} for r in p.records],
    }
