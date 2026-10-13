"""テスト用の食事を作る。"""

from dataclasses import astuple
from datetime import date

import pytest

from domain.meal import FoodItem, Meal
from domain.values import EatenOn, EaterId, MealSlot, Nutrition, Quantity, Source, Unit

EATER = EaterId("eater-1")
LUNCH = EatenOn(date(2026, 10, 12), MealSlot.LUNCH)


def rice(item_id: str = "rice") -> FoodItem:
    return FoodItem(item_id, "白米", Quantity(200, Unit.GRAM), Nutrition(312, 5, 0.6, 74))


def chicken(item_id: str = "chicken") -> FoodItem:
    return FoodItem(item_id, "鶏むね肉", Quantity(100, Unit.GRAM), Nutrition(108, 22, 1.5, 0))


def lunch(meal_id: str = "meal-1", eaten_on: EatenOn = LUNCH, eater: EaterId = EATER) -> Meal:
    return Meal(meal_id, eater, eaten_on, (rice(), chicken()), "白米と鶏むね肉", Source.PHOTO)


def approx(value):
    """小数の誤差を無視して栄養（Nutrition・NutritionGap）を比べる。"""
    return pytest.approx(astuple(value))
