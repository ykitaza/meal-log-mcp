from dataclasses import astuple
from datetime import date

import pytest

from domain.errors import MealError, NotFound
from domain.meal import Meal
from domain.values import EatenOn, MealSlot, Nutrition, Quantity, Source, Unit
from tests.domain.factories import EATER, LUNCH, approx, chicken, lunch, rice


def test_合計は品目の栄養の和():
    assert lunch().total() == Nutrition(420, 27, 2.1, 74)


def test_品目のない食事は作れない():
    with pytest.raises(MealError):
        Meal("m", EATER, LUNCH, (), "", Source.TEXT)


def test_品目の_id_は重複できない():
    with pytest.raises(MealError):
        Meal("m", EATER, LUNCH, (rice("x"), chicken("x")), "", Source.TEXT)


def test_量を変えると栄養も同じ割合で変わる():
    meal = lunch().change_amount("rice", 300)
    assert meal.items[0].quantity == Quantity(300, Unit.GRAM)  # 単位はそのまま
    assert astuple(meal.items[0].nutrition) == approx(Nutrition(468, 7.5, 0.9, 111))
    assert meal.items[1] == chicken()  # ほかの行は変わらない


def test_量は0より大きい():
    with pytest.raises(MealError):
        lunch().change_amount("rice", 0)


def test_変更すると新しい食事を返し元は変わらない():
    meal = lunch()
    meal.change_amount("rice", 300)
    assert meal == lunch()


def test_品目を足して消せる():
    meal = lunch().add_item(rice("rice2")).remove_item("chicken")
    assert [item.id for item in meal.items] == ["rice", "rice2"]


def test_ない品目は指定できない():
    with pytest.raises(NotFound):
        lunch().remove_item("nothing")


def test_最後の品目は消せない():
    with pytest.raises(MealError):
        lunch().remove_item("rice").remove_item("chicken")


def test_日時と区分を移せる():
    dinner = EatenOn(date(2026, 10, 11), MealSlot.DINNER)
    assert lunch().move_to(dinner).eaten_on == dinner


def test_複製は別の食事として記録される():
    tomorrow = EatenOn(date(2026, 10, 13), MealSlot.LUNCH)
    copy = lunch().copy_to("meal-2", tomorrow)
    assert (copy.id, copy.eaten_on, copy.source) == ("meal-2", tomorrow, Source.COPY)
    assert copy.items == lunch().items
