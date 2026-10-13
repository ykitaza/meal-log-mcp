"""MCP のツールを、通信を通さずに呼んで確かめる。アクセストークンは検証済みのものに差し替える。"""

import asyncio
import json
from datetime import date

import pytest
from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver.exceptions import ToolError

from application.goals import GoalService
from application.meals import MealService
from application.summaries import SummaryService
from application.templates import TemplateService
from application.weights import WeightService
from infrastructure import memory_repositories as memory
from infrastructure.subject_as_eater_id import SubjectAsEaterId
from presentation import mcp_server
from presentation.mcp_server import Services, create_mcp_server

TODAY = date(2026, 10, 12)
LUNCH = {
    "date": "2026-10-12",
    "slot": "lunch",
    "items": [
        {"name": "白米", "amount": 200, "unit": "g", "kcal": 312, "protein_g": 5, "fat_g": 0.6, "carbs_g": 74},
        {"name": "鶏むね肉", "amount": 100, "unit": "g", "kcal": 108, "protein_g": 22, "fat_g": 1.5, "carbs_g": 0},
    ],
    "description": "白米と鶏むね肉",
    "source": "photo",
}
GOALS = {
    "policy": "bulk",
    "body_weight_kg": 70,
    "protein_per_kg": 2.0,
    "training_day": {"kcal": 2800, "fat_g": 70, "carbs_g": 380},
    "rest_day": {"kcal": 2400, "fat_g": 70, "carbs_g": 280},
}


class FakeSession:
    def __init__(self):
        self.revoked = []

    async def revoke(self, access_token, client_id):
        self.revoked.append((access_token, client_id))

    def logout_url(self):
        return "https://authz.example/logout"


@pytest.fixture
def call(monkeypatch):
    token = AccessToken(token="t", client_id="c", scopes=["meals:read", "meals:write"], subject="alice")
    monkeypatch.setattr(mcp_server, "get_access_token", lambda: token)
    eaters, meals = SubjectAsEaterId(), memory.InMemoryMealRepository()
    goals, day_types = memory.InMemoryGoalRepository(), memory.InMemoryDayTypeRepository()
    services = Services(
        MealService(eaters, meals),
        TemplateService(eaters, meals, memory.InMemoryMealTemplateRepository()),
        GoalService(eaters, goals, day_types),
        SummaryService(eaters, meals, goals, day_types),
        WeightService(eaters, memory.InMemoryWeightRepository(), goals),
    )
    session = FakeSession()
    mcp = create_mcp_server(services, token_verifier=object(), trusted_issuer="https://authz.example",
                            resource_url="https://meals.example/mcp", today=lambda: TODAY, session=session)

    def _call(tool: str, **arguments):
        result = asyncio.run(mcp.call_tool(tool, arguments))
        return json.loads(result.content[0].text)

    _call.mcp, _call.session = mcp, session
    return _call


def test_記録すると食事と今日の状況を返す(call):
    result = call("record_meal", meal=LUNCH)
    assert result["meals"][0]["total"] == {"kcal": 420, "protein_g": 27, "fat_g": 2.1, "carbs_g": 74}
    assert result["today"]["total"]["kcal"] == 420
    assert "目標が未設定" in result["today"]["note"]


def test_目標を決めると残りが出る(call):
    call("set_goals", **GOALS)
    call("record_meal", meal=LUNCH)
    assert call("today_status")["remaining"] == {"kcal": 1980, "protein_g": 113, "fat_g": 67.9, "carbs_g": 206}
    assert call("set_day_type", day_type="training")["remaining"]["kcal"] == 2380


def test_量を直すと栄養も変わる(call):
    meal = call("record_meal", meal=LUNCH)["meals"][0]
    rice = meal["items"][0]["item_id"]
    updated = call("update_meal", meal_id=meal["meal_id"], change_amounts=[{"item_id": rice, "amount": 100}])
    assert updated["meals"][0]["items"][0]["kcal"] == 156


def test_いつものと昨日と同じ(call):
    meal = call("record_meal", meal=LUNCH)["meals"][0]
    call("save_template", meal_id=meal["meal_id"], name="いつもの昼")
    tomorrow = {"date": "2026-10-13", "slot": "lunch"}
    assert call("record_template", name="いつもの昼", when=tomorrow)["meals"][0]["source"] == "template"
    assert call("copy_meal", meal_id=meal["meal_id"], to=tomorrow)["meals"][0]["source"] == "copy"
    assert len(call("list_meals", start="2026-10-13", end="2026-10-13")["meals"]) == 2


def test_ドメインの決まりに反すると理由を返す(call):
    meal = call("record_meal", meal={**LUNCH, "items": LUNCH["items"][:1]})["meals"][0]
    with pytest.raises(ToolError, match="最後の品目"):
        call("update_meal", meal_id=meal["meal_id"], remove_item_ids=[meal["items"][0]["item_id"]])



def test_週のふり返り(call):
    call("record_meal", meal=LUNCH)
    review = call("weekly_review")
    assert (review["from"], review["to"], review["recorded_days"]) == ("2026-10-06", "2026-10-12", 1)


PROFILE = {"sex": "male", "age": 30, "height_cm": 172, "weight_kg": 67, "daily_activity": "low",
           "training_minutes": 60, "policy": "bulk", "pace_kg_per_week": 0.25, "protein_per_kg": 2.0}


def test_目標の案は保存せず_そのまま_set_goals_に渡せる(call):
    suggestion = call("suggest_goals", **PROFILE)
    assert suggestion["goal"]["rest_day"]["kcal"] == 2200
    assert "note" in call("today_status")  # まだ保存していない
    call("set_goals", **suggestion["set_goals_arguments"])
    assert call("today_status")["target"]["kcal"] == 2200


def test_体のデータが範囲外なら理由を返す(call):
    with pytest.raises(ToolError, match="年齢"):
        call("suggest_goals", **{**PROFILE, "age": 5})


def test_目標を決めるときに聞く項目を返し_必須は方針だけ(call):
    result = call("goal_questions")
    required = [q["name"] for q in result["questions"] if q.get("required")]
    assert required == ["policy"] and result["current_goal"] is None


def test_ログアウトは本人のトークンで連携を取り消し_リンクを返す(call):
    result = call("logout")
    assert call.session.revoked == [("t", "c")]
    assert result["logout_url"] == "https://authz.example/logout"


def test_方針だけでも目標を設定できる(call):
    suggestion = call("suggest_goals", policy="maintain")
    assert suggestion["goal"]["rest_day"] == {"kcal": None, "protein_g": None, "fat_g": None, "carbs_g": None}
    assert suggestion["used"] == {"sex": "unspecified"}
    call("set_goals", **suggestion["set_goals_arguments"])
    status = call("today_status")
    assert "note" not in status and status["remaining"]["kcal"] is None


def test_体重を記録すると道のりを返し_目標体重までの残りが出る(call):
    call("set_goals", policy="bulk", target_weight_kg=70)
    call("record_weight", kg=66.0, day="2026-09-28")
    result = call("record_weight", kg=67.0)  # 今日
    assert (result["latest"]["kg"], result["remaining_kg"], result["weekly_change_kg"]) == (67.0, 3.0, 0.5)
    assert result["weeks_to_goal"] == 6.0 and result["on_track"] is True
    assert len(call("goal_progress")["records"]) == 2


def test_結果に次の提案がある(call):
    assert call("record_meal", meal=LUNCH)["suggested_next"]
    week = call("weekly_review")
    assert week["suggested_next"] and week["days"][-1]["recorded"] is True


def test_方針だけの目標も今日と週の結果に出る(call):
    call("set_goals", policy="bulk")
    assert call("today_status")["goal"]["policy"] == "bulk"
    assert call("weekly_review")["goal"]["policy"] == "bulk"
