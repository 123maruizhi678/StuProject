"""仅提供企业学生查询、成绩业务及其 NL2SQL 联调入口。"""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Path, Query
from sqlalchemy.orm import Session

from app.core.response import success
from app.database import get_db
from app.models.enterprise_student import Employee
from app.schemas.enterprise_student import NaturalQuery, ScoreCreate, ScorePatch, ScoreVoid
from app.services import enterprise_student as service

router = APIRouter(prefix="/enterprise", tags=["enterprise-students-scores"])
DB = Annotated[Session, Depends(get_db)]
Actor = Annotated[Employee, Depends(service.current_employee)]
EntityID = Annotated[int, Path(gt=0)]
RequestKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")]
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get("/students")
def students(db: DB, actor: Actor, page: Page = 1, page_size: PageSize = 20,
             keyword: Annotated[str | None, Query(max_length=100)] = None,
             student_no: Annotated[str | None, Query(max_length=32)] = None,
             department_id: Annotated[int | None, Query(gt=0)] = None,
             status: Annotated[str | None, Query(max_length=32)] = None, is_archived: bool = False):
    return success(service.list_students(db, actor, page=page, page_size=page_size, keyword=keyword,
        student_no=student_no, department_id=department_id, status=status, is_archived=is_archived))


@router.get("/students/{student_id}")
def student(student_id: EntityID, db: DB, actor: Actor):
    return success(service.get_student(db, actor, student_id))


@router.post("/scores")
def create_score(payload: ScoreCreate, db: DB, actor: Actor, request_key: RequestKey):
    return success(service.mutate_score(db, actor, "score.create", payload, request_key))


@router.get("/scores")
def scores(db: DB, actor: Actor, page: Page = 1, page_size: PageSize = 20,
           student_id: Annotated[int | None, Query(gt=0)] = None,
           course_code: Annotated[str | None, Query(max_length=64)] = None,
           term_code: Annotated[str | None, Query(max_length=32)] = None,
           assessment_code: Annotated[str | None, Query(max_length=64)] = None,
           attempt_no: Annotated[int | None, Query(ge=1)] = None,
           status: Literal["valid", "void"] = "valid"):
    return success(service.list_scores(db, actor, page=page, page_size=page_size, student_id=student_id,
        course_code=course_code, term_code=term_code, assessment_code=assessment_code, attempt_no=attempt_no, status=status))


@router.get("/scores/{score_id}")
def score(score_id: EntityID, db: DB, actor: Actor):
    return success(service.get_score(db, actor, score_id))


@router.patch("/scores/{score_id}")
def patch_score(score_id: EntityID, payload: ScorePatch, db: DB, actor: Actor, request_key: RequestKey):
    return success(service.mutate_score(db, actor, "score.correct", payload, request_key, score_id))


@router.post("/scores/{score_id}/void")
def void_score(score_id: EntityID, payload: ScoreVoid, db: DB, actor: Actor, request_key: RequestKey):
    return success(service.mutate_score(db, actor, "score.void", payload, request_key, score_id))


@router.post("/student-scores/nl-query")
async def natural_query(payload: NaturalQuery, db: DB, actor: Actor):
    from app.services.enterprise_nl2sql import query_student_scores
    return success(await query_student_scores(db, actor, payload.question))
