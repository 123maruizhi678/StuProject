"""学生及成绩请求。禁止在更正接口修改成绩业务键。"""
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
ScoreNumber = Annotated[Decimal, Field(ge=0, max_digits=8, decimal_places=2, allow_inf_nan=False)]


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScoreCreate(StrictRequest):
    student_id: int = Field(gt=0)
    course_code: Code
    term_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
    assessment_code: Code
    attempt_no: int = Field(default=1, ge=1, strict=True)
    score_value: ScoreNumber
    max_score: ScoreNumber

    @model_validator(mode="after")
    def valid_range(self):
        if self.max_score <= 0 or self.score_value > self.max_score:
            raise ValueError("要求 max_score > 0 且 0 <= score_value <= max_score")
        return self


class ScorePatch(StrictRequest):
    score_value: ScoreNumber | None = None
    max_score: ScoreNumber | None = None
    change_reason: Reason
    expected_version: int = Field(ge=1, strict=True)

    @model_validator(mode="after")
    def has_changes(self):
        if self.score_value is None and self.max_score is None:
            raise ValueError("至少提供 score_value 或 max_score")
        if any(getattr(self, key) is None for key in self.model_fields_set & {"score_value", "max_score"}):
            raise ValueError("成绩字段不能为 null")
        return self


class ScoreVoid(StrictRequest):
    change_reason: Reason
    expected_version: int = Field(ge=1, strict=True)


class NaturalQuery(StrictRequest):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
