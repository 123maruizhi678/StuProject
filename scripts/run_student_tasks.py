"""只运行学生模块任务；--once 单次执行，--sync 同时拉取已绑定学生的教务/CRM。"""

import argparse
import json
import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select, or_
from pydantic import ValidationError
from app.config import settings
from app.database import SessionLocal
from app.core.student_auth import Principal
from app.core.response import BusinessException
from app.models.student_shared import student_profile
from app.services.student_clients import StudentSourceClient
from app.services.student_sync import StudentSyncService
from app.schemas.student import AcademicBatch, ProgressBatch
from app.tasks.student_tasks import StudentTasks


def sync_sources():
    stats = {"sync_succeeded": 0, "sync_failed": 0}
    actor = Principal("service", service_code="student.sync", scopes=("student:sync",))
    with SessionLocal() as db:
        # 分页扫描，避免把所有学生一次载入内存；网络请求不持有数据库写锁。
        after_id = 0
        while True:
            rows = (
                db.execute(
                    select(student_profile)
                    .where(
                        student_profile.c.student_id > after_id,
                        student_profile.c.is_archived.is_(False),
                        or_(
                            student_profile.c.external_student_id.is_not(None),
                            student_profile.c.crm_student_id.is_not(None),
                        ),
                    )
                    .order_by(student_profile.c.student_id)
                    .limit(100)
                )
                .mappings()
                .all()
            )
            db.rollback()
            if not rows:
                break
            for student in rows:
                after_id = student["student_id"]
                for kind, configured in (
                    ("academic", settings.STUDENT_EDUCATION_URL),
                    ("progress", settings.STUDENT_CRM_URL),
                ):
                    identity_field = (
                        "external_student_id"
                        if kind == "academic"
                        else "crm_student_id"
                    )
                    if not configured or not student[identity_field]:
                        continue
                    try:
                        data = StudentSourceClient().fetch(kind, student)
                        model = AcademicBatch if kind == "academic" else ProgressBatch
                        batch = model.model_validate(
                            {
                                "student_id": student["student_id"],
                                "source_system": data["source_system"],
                                "records": data["records"],
                            }
                        )
                        service = StudentSyncService(db)
                        key = "pull:" + uuid4().hex
                        if kind == "academic":
                            service.academic(actor, key, batch)
                        else:
                            service.application(actor, key, batch)
                        stats["sync_succeeded"] += 1
                    except (BusinessException, ValidationError, KeyError):
                        db.rollback()
                        stats["sync_failed"] += 1
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()
    if args.interval < 1:
        parser.error("interval必须为正数")
    tasks, next_sync = StudentTasks(SessionLocal), 0.0
    while True:
        result = tasks.run_once()
        if args.sync and time.monotonic() >= next_sync:
            result.update(sync_sources())
            next_sync = time.monotonic() + max(
                1, settings.STUDENT_SYNC_INTERVAL_SECONDS
            )
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
