from datetime import date, time

import pytest

from domain.errors import MealError
from domain.values import EatenOn, MealSlot, Nutrition, NutritionGap, Quantity, Unit


def test_栄養は足し算と倍数ができる():
    total = Nutrition(100, 10, 5, 20) + Nutrition(50, 2, 1, 10)
    assert total == Nutrition(150, 12, 6, 30)
    assert total.times(2) == Nutrition(300, 24, 12, 60)


def test_栄養の差は負になりうる():
    assert Nutrition(100, 10, 5, 20).minus(Nutrition(150, 4, 5, 20)) == NutritionGap(-50, 6, 0, 0)


def test_栄養は負にできない():
    with pytest.raises(MealError):
        Nutrition(-1, 0, 0, 0)


def test_量は0より大きい():
    with pytest.raises(MealError):
        Quantity(0, Unit.GRAM)


@pytest.mark.parametrize(
    ("hour", "slot"),
    [
        (5, MealSlot.BREAKFAST),
        (9, MealSlot.BREAKFAST),
        (10, MealSlot.LUNCH),
        (15, MealSlot.SNACK),
        (17, MealSlot.DINNER),
        (22, MealSlot.SNACK),
        (2, MealSlot.SNACK),
    ],
)
def test_時刻から区分を決める(hour, slot):
    assert MealSlot.from_time(time(hour, 30)) == slot


def test_時刻なしでも食べたときを表せる():
    eaten_on = EatenOn(date(2026, 10, 12), MealSlot.LUNCH)
    assert eaten_on.at is None


def test_時刻があれば区分は時刻から決まる():
    assert EatenOn.from_time(date(2026, 10, 12), time(19, 0)).slot == MealSlot.DINNER
