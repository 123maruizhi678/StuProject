"""客户研判八接口 + 受控原件下载。

统一返回 `{code, message, data}`；受控原件下载返回二进制流。
"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from fastapi import Query
from app.models.customer import CustomerSource, Product

from app.models.common.user_account import UserAccount as AccountContext
from app.core.common.authorization import require_permission
from app.core.common.response import success
from app.database import get_db
from app.schemas.customer.customer import (
    JudgeBatchRequest,
    JudgeRequest,
    ParseRequest,
    ResultListQuery,
    RuleUpdate,
)
from app.services.customer.customer_service import (
    CustomerService,
    serialize_info,
    serialize_result,
    serialize_rule,
    serialize_source,
)

router = APIRouter(prefix="/api/v1/customer", tags=["customer"])


@router.get("/source")
def list_sources(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                 account=Depends(require_permission("customer.source.parse")), db=Depends(get_db)):
    rows = db.scalars(select(CustomerSource).order_by(CustomerSource.id.desc()).limit(limit).offset(offset)).all()
    return success({"items": [serialize_source(row) for row in rows],
                    "total": db.scalar(select(func.count()).select_from(CustomerSource)), "limit": limit, "offset": offset})


@router.get("/source/{source_id}")
def get_source(source_id: int, account=Depends(require_permission("customer.source.parse")), db=Depends(get_db)):
    from app.services.customer.errors import NotFoundError
    row = db.get(CustomerSource, source_id)
    if row is None:
        raise NotFoundError("资料来源不存在")
    from app.repositories.customer.customer_repository import list_info_by_source
    return success({"source": serialize_source(row), "fields": [serialize_info(i) for i in list_info_by_source(db, source_id)]})


@router.get("/product")
def list_products(account=Depends(require_permission("customer.rule.read")), db=Depends(get_db)):
    rows = db.scalars(select(Product).order_by(Product.id)).all()
    return success([{c.name: getattr(row, c.name) for c in Product.__table__.c} for row in rows])


@router.post("/source")
def create_source(
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    account: AccountContext = Depends(require_permission("customer.source.create")),
    db: Session = Depends(get_db),
):
    service = CustomerService(db)
    if file is not None:
        source = service.create_source(account, file_name=file.filename, file_bytes=file.file.read())
    else:
        source = service.create_source(account, text=text)
    return success(serialize_source(source))


@router.post("/source/{source_id}/parse")
def parse_source(
    source_id: int,
    body: ParseRequest,
    account: AccountContext = Depends(require_permission("customer.source.parse")),
    db: Session = Depends(get_db),
):
    source, infos = CustomerService(db).parse_source(account, source_id, body)
    return success({
        "source": serialize_source(source),
        "fields": [serialize_info(i) for i in infos],
    })


@router.get("/source/{source_id}/file")
def download_source(
    source_id: int,
    account: AccountContext = Depends(require_permission("customer.source.file")),
    db: Session = Depends(get_db),
):
    source = CustomerService(db).get_source_file(account, source_id)
    return FileResponse(source.file_path, filename=source.file_name,
                        media_type="application/octet-stream")


@router.post("/judge")
def judge(
    body: JudgeRequest,
    account: AccountContext = Depends(require_permission("customer.judge.create")),
    db: Session = Depends(get_db),
):
    result = CustomerService(db).judge(account, body)
    return success(serialize_result(result))


@router.post("/judge/batch")
def judge_batch(
    body: JudgeBatchRequest,
    account: AccountContext = Depends(require_permission("customer.judge.batch")),
    db: Session = Depends(get_db),
):
    outcomes = CustomerService(db).batch(account, body)
    return success(outcomes)


@router.get("/result/{result_id}")
def get_result(
    result_id: int,
    account: AccountContext = Depends(require_permission("customer.result.read")),
    db: Session = Depends(get_db),
):
    result = CustomerService(db).get_result(account, result_id)
    return success(serialize_result(result))


@router.get("/result")
def list_results(
    q: ResultListQuery = Depends(),
    account: AccountContext = Depends(require_permission("customer.result.read")),
    db: Session = Depends(get_db),
):
    data = CustomerService(db).list_results(account, q)
    data["items"] = [serialize_result(i) for i in data["items"]]
    return success(data)


@router.get("/rule")
def list_rules(
    account: AccountContext = Depends(require_permission("customer.rule.read")),
    db: Session = Depends(get_db),
):
    service = CustomerService(db)
    rules = service.list_rules(account)
    codes = service.product_code_map()
    return success([serialize_rule(r, codes.get(r.product_id)) for r in rules])


@router.put("/rule")
def update_rule(
    body: RuleUpdate,
    account: AccountContext = Depends(require_permission("customer.rule.manage")),
    db: Session = Depends(get_db),
):
    rule = CustomerService(db).update_rule(account, body)
    return success(serialize_rule(rule, body.product_code))
