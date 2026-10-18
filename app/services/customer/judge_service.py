"""画像研判规则引擎：加载规则、逐条比对、评分。

rule_content 结构：
{
  "match_logic": "all",            // "all"(AND) | "any"(OR)
  "conditions": [                  // 条件列表
    {"field": "education_level", "op": "in", "value": ["本科","硕士","博士"]},
    {"field": "work_years", "op": "ge", "value": 3}
  ],
  "score_rules": [                 // 可选评分（命中依据）
    {"field": "education_level", "points": {"硕士": 40, "本科": 30}},
    {"field": "work_years", "points": {"5": 30, "3": 20}}   // 数值阈值，>=5 得 30，>=3 得 20
  ],
  "score_threshold": 60            // 可选：评分不达阈值视为未命中
}

命中 / 未命中均为正常业务结果；无有效规则、产品停用或规则格式错误时不得生成
正常结论。
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.services.customer.errors import ConflictError, NotFoundError
from app.repositories.customer import customer_repository
from app.models.customer.customer_info import CustomerInfo


def _satisfies(actual, op: str, expected) -> bool:
    """单条件判定。"""
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "in":
        return actual in expected
    if op == "not_in":
        return actual not in expected
    if op in ("ge", "gt", "le", "lt"):
        try:
            a = float(actual)
            b = float(expected)
        except (TypeError, ValueError):
            return False
        return {"ge": a >= b, "gt": a > b, "le": a <= b, "lt": a < b}[op]
    if op == "contains":
        return expected in str(actual or "")
    if op == "is_null":
        return actual is None
    if op == "not_null":
        return actual is not None
    return False


def _evaluate(rule_content: dict, info: CustomerInfo) -> tuple[bool, list, list, Optional[float]]:
    """评估规则，返回 (matched, matched_fields, unmatched_reasons, score)。"""
    conditions = rule_content.get("conditions") or []
    match_logic = rule_content.get("match_logic", "all")
    matched_fields: list = []
    unmatched_reasons: list = []

    for cond in conditions:
        field = cond.get("field")
        if not field:
            continue
        actual = getattr(info, field, None)
        ok = _satisfies(actual, cond.get("op", "eq"), cond.get("value"))
        if ok:
            matched_fields.append(field)
        else:
            unmatched_reasons.append(f"{field} 不满足")

    if match_logic == "any":
        rules_matched = len(matched_fields) > 0
    else:
        rules_matched = len(unmatched_reasons) == 0 and len(conditions) > 0

    score: Optional[float] = _compute_score(rule_content.get("score_rules") or [], info)

    threshold = rule_content.get("score_threshold")
    matched = rules_matched
    if threshold is not None and score is not None:
        matched = matched and score >= float(threshold)

    return matched, matched_fields, unmatched_reasons, score


def _compute_score(score_rules: list, info: CustomerInfo) -> Optional[float]:
    if not score_rules:
        return None
    total = 0.0
    for sr in score_rules:
        field = sr.get("field")
        points = sr.get("points") or {}
        actual = getattr(info, field, None)
        if actual is None:
            continue
        # 数值阈值：keys 为数字字符串，从大到小匹配第一个满足的
        numeric_keys = sorted(
            [k for k in points.keys() if str(k).replace(".", "", 1).isdigit()],
            key=lambda x: float(x),
            reverse=True,
        )
        if numeric_keys:
            for k in numeric_keys:
                try:
                    if float(actual) >= float(k):
                        total += float(points[k])
                        break
                except (TypeError, ValueError):
                    continue
        # 字符串精确匹配
        elif str(actual) in points:
            total += float(points[str(actual)])
    return round(total, 2)


class JudgeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def judge(self, customer_info_id: int, product_code: str,
              rule_version: Optional[str] = None, operator_id: Optional[int] = None):
        info = customer_repository.get_info(self.db, customer_info_id)
        if info is None:
            raise NotFoundError("客户字段记录不存在")
        product = customer_repository.get_product_by_code(self.db, product_code)
        if product is None:
            raise NotFoundError("产品不存在")
        if product.status != "active":
            raise ConflictError("产品已停用，无法研判")
        rule = (
            customer_repository.get_rule(self.db, product.id, rule_version)
            if rule_version
            else customer_repository.get_active_rule(self.db, product.id)
        )
        if rule is None:
            raise NotFoundError("无可用规则")
        # 同一信息 + 产品 + 规则版本复用既有结果（业务幂等）
        existing = customer_repository.get_result(self.db, info.id, product.id, rule.rule_version)
        if existing is not None:
            return existing
        matched, matched_fields, unmatched, score = _evaluate(rule.rule_content or {}, info)
        result = customer_repository.create_result(
            self.db,
            source_id=info.source_id,
            customer_info_id=info.id,
            product_id=product.id,
            rule_version=rule.rule_version,
            input_snapshot={
                "full_name": info.full_name,
                "education_level": info.education_level,
                "major": info.major,
                "work_years": info.work_years,
                "industry": info.industry,
                "city": info.city,
                "income_level": info.income_level,
                "target_product_code": info.target_product_code,
            },
            matched=matched,
            matched_fields=matched_fields,
            unmatched_reasons=unmatched,
            score=score,
            created_by=operator_id,
        )
        return result

    def batch(self, customer_info_ids: list, product_code: str,
              operator_id: Optional[int] = None):
        """批量研判：逐条执行；外层负责 savepoint 与提交。"""
        results = []
        for info_id in customer_info_ids:
            results.append(self.judge(info_id, product_code, operator_id=operator_id))
        return results
