"""研判八接口 + 受控原件下载的请求 / 响应契约。"""

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    force: bool = False
    expected_version: Optional[int] = None


class JudgeRequest(BaseModel):
    customer_info_id: int
    product_code: str
    rule_version: Optional[str] = None


class JudgeBatchRequest(BaseModel):
    customer_info_ids: List[int] = Field(..., min_length=1)
    product_code: str


class RuleUpdate(BaseModel):
    """发布新规则版本。"""

    product_code: str
    rule_content: Any
    rule_description: Optional[str] = None
    is_active: bool = True
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None


# ---- 结果列表查询参数 ----
class ResultListQuery(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)
    product_code: Optional[str] = None
    matched: Optional[bool] = None
