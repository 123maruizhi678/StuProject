"""受控本地课程主数据与本人选课关系；不从成绩或招生项目猜测选课。"""
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.config import settings
from app.core.common.response import BusinessException


class Course(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    course_code: str = Field(min_length=1, max_length=64)
    course_name: str = Field(min_length=1, max_length=200)


class Enrollment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    student_id: int = Field(gt=0)
    course_code: str = Field(min_length=1, max_length=64)
    term_code: str = Field(min_length=1, max_length=32)
    status: Literal['active', 'inactive'] = 'active'


class Catalog(BaseModel):
    model_config = ConfigDict(extra='forbid')
    courses: list[Course]
    enrollments: list[Enrollment]


def own_courses(student_id, limit=20, offset=0):
    try:
        catalog = Catalog.model_validate(json.loads(settings.STUDENT_COURSES_FILE.read_text(encoding='utf-8')))
        names = {c.course_code: c.course_name for c in catalog.courses}
        if len(names) != len(catalog.courses):
            raise ValueError('duplicate course')
        seen, rows = set(), []
        for item in catalog.enrollments:
            key = (item.student_id, item.course_code, item.term_code)
            if key in seen or item.course_code not in names:
                raise ValueError('invalid enrollment')
            seen.add(key)
            if item.student_id == student_id and item.status == 'active':
                rows.append({**item.model_dump(exclude={'student_id'}), 'course_name': names[item.course_code]})
        rows.sort(key=lambda r: (r['term_code'], r['course_code']))
        return {'items': rows[offset:offset+limit], 'total': len(rows), 'limit': limit, 'offset': offset}
    except (OSError, ValueError, TypeError):
        raise BusinessException('本地课程与选课权威来源尚未就绪', 503) from None
