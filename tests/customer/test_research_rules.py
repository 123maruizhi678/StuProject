"""研判规则引擎单元测试（纯函数，无 DB 依赖）。"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.customer.judge_service import _compute_score, _evaluate, _satisfies


def _info(**kw):
    base = dict(
        full_name=None, gender=None, age=None, education_level=None, major=None,
        work_years=None, industry=None, position_title=None, city=None,
        income_level=None, target_product_code=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_satisfies_ops():
    assert _satisfies(5, "ge", 3) is True
    assert _satisfies(2, "ge", 3) is False
    assert _satisfies("硕士", "in", ["本科", "硕士"]) is True
    assert _satisfies("博士", "in", ["本科", "硕士"]) is False
    assert _satisfies("北京", "contains", "京") is True
    assert _satisfies(None, "is_null", None) is True
    assert _satisfies("x", "not_null", None) is True


def test_evaluate_all_matched():
    rule = {
        "match_logic": "all",
        "conditions": [
            {"field": "education_level", "op": "in", "value": ["本科", "硕士"]},
            {"field": "work_years", "op": "ge", "value": 3},
        ],
        "score_rules": [],
    }
    info = _info(education_level="硕士", work_years=5)
    matched, mf, ur, score = _evaluate(rule, info)
    assert matched is True
    assert set(mf) == {"education_level", "work_years"}
    assert ur == []


def test_evaluate_any():
    rule = {
        "match_logic": "any",
        "conditions": [
            {"field": "age", "op": "ge", "value": 50},
            {"field": "income_level", "op": "eq", "value": "高"},
        ],
        "score_rules": [],
    }
    info = _info(age=30, income_level="高")
    matched, mf, ur, score = _evaluate(rule, info)
    assert matched is True
    assert "income_level" in mf


def test_score_threshold_gates_match():
    rule = {
        "match_logic": "all",
        "conditions": [{"field": "work_years", "op": "ge", "value": 3}],
        "score_rules": [{"field": "work_years", "points": {"10": 30, "5": 20, "3": 10}}],
        "score_threshold": 50,
    }
    info = _info(work_years=6)
    matched, mf, ur, score = _evaluate(rule, info)
    assert score == 20.0
    assert matched is False  # 条件满足但评分不达阈值


def test_compute_score_numeric_and_string():
    info = _info(education_level="博士", work_years=12)
    score = _compute_score(
        [
            {"field": "education_level", "points": {"博士": 50, "硕士": 40}},
            {"field": "work_years", "points": {"10": 30, "5": 20, "3": 10}},
        ],
        info,
    )
    assert score == 80.0


def test_empty_conditions_not_matched():
    rule = {"match_logic": "all", "conditions": [], "score_rules": []}
    matched, mf, ur, score = _evaluate(rule, _info(age=30))
    assert matched is False
