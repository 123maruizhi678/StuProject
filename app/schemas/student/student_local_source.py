"""本地教务/CRM维护输入；身份和源时间由服务端产生。"""
from app.schemas.student.student import AcademicRecord, ProgressRecord, AwareDatetime, Field

class LocalAcademic(AcademicRecord):
    external_event_id: str | None = None
    source_updated_at: AwareDatetime | None = None
    id: int | None = Field(default=None,gt=0)
    expected_version: int | None = Field(default=None,ge=1)


class LocalProgress(ProgressRecord):
    source_updated_at: AwareDatetime | None = None
    id: int | None = Field(default=None,gt=0)
    expected_updated_at: AwareDatetime | None = None
