"""客服 Agent 模块的请求 / 响应模型。"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str | None = None
    user_id: str | None = None
    message: str = Field(..., min_length=1, description="访客消息")


class ChatAction(BaseModel):
    type: str = Field(..., description="动作类型，如 show_events / show_courses")
    payload: dict = Field(default_factory=dict, description="动作附加参数")


class ChatData(BaseModel):
    session_id: str
    intent: str
    reply: str
    need_action: bool = False
    action: ChatAction | None = None


class EventItem(BaseModel):
    event_id: int
    event_name: str
    event_type: str
    start_time: str
    location: str
    signup_method: str
    quota: int
    signed_count: int
    status: str


class SignupRequest(BaseModel):
    event_id: int
    customer_name: str = Field(..., min_length=1)
    customer_phone: str = Field(..., min_length=1)
    customer_info: dict | None = None


class SignupData(BaseModel):
    signup_id: int
    signup_time: str


class CourseItem(BaseModel):
    course_id: int
    course_name: str
    category: str
    target_audience: str
    description: str
    location: str
    signup_method: str


class FaqData(BaseModel):
    question: str
    answer: str
    category: str
