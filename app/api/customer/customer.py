"""客户研判八接口 + 受控原件下载。

统一返回 `{code, message, data}`；受控原件下载返回二进制流。
"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import Query
from app.models.customer import Product

from app.models.common.user_account import UserAccount as AccountContext
from app.core.common.authorization import require_permission
from app.core.common.research_access import require_research_read
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
                 account=Depends(require_research_read("customer.source.read")), db=Depends(get_db)):
    return success(CustomerService(db).list_sources(account, limit, offset))


@router.get("/source/{source_id}")
def get_source(source_id: int, account=Depends(require_research_read("customer.source.read")), db=Depends(get_db)):
    return success(CustomerService(db).get_source_detail(account, source_id))


@router.get("/product")
def list_products(account=Depends(require_research_read("customer.rule.read")), db=Depends(get_db)):
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
        source = service.create_source(account, file_name=file.filename, file_bytes=file.file.read(20*1024*1024+1))
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
    account: AccountContext = Depends(require_research_read("customer.result.read")),
    db: Session = Depends(get_db),
):
    result = CustomerService(db).get_result(account, result_id)
    return success(serialize_result(result))


@router.get("/result")
def list_results(
    q: ResultListQuery = Depends(),
    account: AccountContext = Depends(require_research_read("customer.result.read")),
    db: Session = Depends(get_db),
):
    data = CustomerService(db).list_results(account, q)
    data["items"] = [serialize_result(i) for i in data["items"]]
    return success(data)


@router.get("/rule")
def list_rules(
    account: AccountContext = Depends(require_research_read("customer.rule.read")),
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


# 当前文件画像入口：与既有可配置产品记录隔离，不重写历史产品或数据库规则。
from app.schemas.customer.profile import ProfileEvaluationRequest
from app.services.customer.profile_rules import catalog, evaluate_profile
from app.services.customer.profile_input import preview_input


@router.get("/profile/catalog")
def profile_catalog(account=Depends(require_research_read("customer.rule.read"))):
    return success(catalog())


@router.post("/profile/analyze")
def profile_analyze(
    text: Optional[str] = Form(None), file: Optional[UploadFile] = File(None),
    account=Depends(require_permission("customer.judge.create")),
):
    # 不持久化原件或分析结果；保存来源仍由既有来源接口显式发起。
    return success(preview_input(text=text, file_name=file.filename if file else None,
        file_bytes=file.file.read(20*1024*1024+1) if file else None))


@router.post("/profile/evaluate")
def profile_evaluate(body: ProfileEvaluationRequest,
                     account=Depends(require_permission("customer.judge.create"))):
    return success(evaluate_profile(body.facts.model_dump(exclude_none=True)))


@router.get("/source/{source_id}/profile")
def source_profile(source_id: int,
                   account=Depends(require_research_read("customer.source.read")), db=Depends(get_db)):
    detail=CustomerService(db).get_source_detail(account,source_id)
    items=[]
    for info in detail["fields"]:
        items.append({"customer_info_id":info["id"], "row_number":info.get("profile_row_number") or len(items)+1,
                      "sheet_name":info.get("profile_sheet_name", ""),
                      "facts":info["profile_fields"], "warnings":info.get("profile_warnings", []),
                      "error":None,"evaluation":evaluate_profile(info["profile_fields"])})
    return success({"source":detail["source"],"items":items,"total":len(items),"persisted":False,
                    "notice":"按文件规则实时计算；保存的来源资料保持不变，本次输出不是历史结果快照"})
