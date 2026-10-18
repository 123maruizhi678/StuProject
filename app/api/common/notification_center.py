from typing import Literal
from fastapi import APIRouter, Depends, Query
from app.database import get_db
from app.core.common.auth import get_current_account
from app.core.common.admin_authorization import require_platform_admin
from app.core.common.response import success
from app.schemas.common.notification_center import AnnouncementWrite
from app.services.common import notification_center as service

router = APIRouter(prefix="/common", tags=["公共通知中心"])


@router.get("/announcements")
def announcements(db=Depends(get_db), account=Depends(get_current_account)):
    return success(service.announcement_list(db, account))


@router.get("/announcements/manage")
def manage_announcements(db=Depends(get_db), account=Depends(require_platform_admin)):
    return success(service.announcement_list(db, account, manage=True))


@router.post("/announcements")
def create_announcement(payload: AnnouncementWrite, db=Depends(get_db), account=Depends(require_platform_admin)):
    return success(service.save_announcement(db, account, payload))


@router.patch("/announcements/{announcement_id}")
def edit_announcement(announcement_id: int, payload: AnnouncementWrite, db=Depends(get_db), account=Depends(require_platform_admin)):
    return success(service.save_announcement(db, account, payload, announcement_id))


@router.get("/notifications")
def notifications(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                  unread: bool = False, kind: Literal["status", "reply", "important"] | None = None,
                  q: str = Query("", max_length=200), db=Depends(get_db), account=Depends(get_current_account)):
    return success(service.personal_list(db, account, limit=limit, offset=offset, unread=unread, kind=kind, query=q.strip()))


@router.get("/notifications/{key}")
def notification_detail(key: str, db=Depends(get_db), account=Depends(get_current_account)):
    return success(service.message_detail(db, account, key))


@router.post("/notifications/{key}/read")
def read_notification(key: str, db=Depends(get_db), account=Depends(get_current_account)):
    return success(service.mark_read(db, account, key))
