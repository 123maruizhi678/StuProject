"""文件画像事实契约。补充信息复用 customer_info.raw_fields，不新增表或列。"""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Country = Literal['新加坡', '德国']


class ProfileFacts(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    full_name: Text | None = None
    age: Annotated[int, Field(ge=0, le=120)] | None = None
    education_level: Text | None = None
    education_status: Literal['在读', '毕业'] | None = None
    grade: Text | None = None
    preferred_countries: list[Country] | None = Field(None, max_length=2)
    excluded_countries: list[Country] | None = Field(None, max_length=2)
    study_abroad_willingness: bool | None = None
    education_goal: bool | None = None
    employment_goal: bool | None = None
    immigration_goal: bool | None = None
    family_support: bool | None = None
    budget_rmb: Annotated[float, Field(ge=0, le=100000000, allow_inf_nan=False)] | None = None
    german_level: Literal['A0', 'A1', 'A2', 'B1', 'B2', 'C1', 'C2'] | None = None
    german_learning_willingness: bool | None = None
    german_expression_ability: bool | None = None
    practical_ability: bool | None = None
    logical_ability: bool | None = None
    closed_training_willingness: bool | None = None
    entrance_test_willingness: bool | None = None


class ProfileEvaluationRequest(BaseModel):
    facts: ProfileFacts


PROFILE_FIELDS = frozenset(ProfileFacts.model_fields)
