"""管理员开户文档只追加；快照和前缀校验确保六份原文逐字节保留。"""
from pathlib import Path
import argparse,hashlib,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.config import BASE_DIR

FILES=['操作文档.md','企业管理模块_本地实施方案.md','企业管理模块_接口测试数据.md','企业管理模块_接口清单.md','企业管理模块_实施记录.md','项目目录架构_最终汇总.md']
FOLDER=BASE_DIR/'.runtime/registration-doc-originals'
MARKER='## 管理员统一注册接口实施补充（2026-10-17）'

def snapshot():
    FOLDER.mkdir(parents=True,exist_ok=True)
    manifest={}
    for name in FILES:
        content=(BASE_DIR/'开发文档'/name).read_bytes()
        target=FOLDER/name
        if target.exists():
            original=target.read_bytes()
            if not content.startswith(original):raise RuntimeError(name+'原文前缀与已有快照不一致')
        else:target.write_bytes(content);original=content
        manifest[name]={'original_bytes':len(original),'sha256':hashlib.sha256(original).hexdigest()}
    (FOLDER/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'snapshotted_files':len(manifest),'originals_preserved':True},ensure_ascii=False))

def verify():
    for name in FILES:
        if not (BASE_DIR/'开发文档'/name).read_bytes().startswith((FOLDER/name).read_bytes()):raise RuntimeError(name+'原文被修改')
    print(json.dumps({'checked_files':len(FILES),'original_byte_prefix_unchanged':True},ensure_ascii=False))

def append():
    common='''
本段为本次管理员开户的实际增量，追加于原文之后；原有章节、接口和历史实施状态保持原样，当前新增能力以本段为准。

统一开户接口为`POST /api/v1/auth/register`，仅`user_account.identity_type=admin`的平台管理员可以调用。员工的admin业务角色不能使用；未登录返回HTTP401，其他有效身份返回HTTP403。公共`/openapi.json`、`/docs`及`/redoc`不展示此接口及其注册Schema；管理员在开户页面加载受保护的`GET /api/v1/admin/openapi.json`查看文档。

支持admin、employee、student、customer四类账户。平台管理员只写user_account；员工同步写employee并绑定employee_id；学生同步写student_profile并绑定student_id；客户同步写customer_profile并绑定customer_id。员工／学生／客户均支持profile新建档案或对应ID绑定已有档案，两者必须且只能提供一个，不通过绑定入口覆盖已有姓名、部门或职位。

新账户初始密码固定为123456；客户端不传password／password_hash／role_codes，数据库只保存Argon2哈希。此默认值只用于新开户，不重置现有admin账户密码。成功返回账户ID、用户名、身份、档案ID、部门及权限，审计不记录明文密码或密码哈希。

注册需携带8—128位可见ASCII的Idempotency-Key。同一管理员、同一键和相同请求返回原成功回执；同键不同参数返回业务409；重复用户名、工号、学号或重复绑定也返回409。档案、职位角色、账户及审计同事务提交，失败整体回滚。开户审计复用operation_log，service_code=auth.account.registration，operator_user_id写入受控快照，不伪造员工操作者。

员工注册要求员工及部门有效，并以数据库受控position_title映射role_codes：普通员工→employee；顾问／招生顾问／咨询顾问→employee+consultant；部门主管／部门经理→employee+manager；老师／教师／班主任→employee+teacher；教务／教务专员→employee+academic；企业管理员／企业配置管理员→employee+admin。未知或空职位拒绝开户。职位变更时按role.manage授权同步角色、版本和审计，禁止本人改变自身授权职位；手工角色配置不能与职位映射冲突。主管范围仍取employee.department_id，不自动含子部门；老师／教务仍需学生及课程绑定。

新学生默认status=active、is_archived=0；已有学生必须有效且未归档，已归档或已绑定账户拒绝开户。客户也要求未归档；新客户顾问若填写，须为同部门有效consultant。登录和每次JWT访问重新校验员工、部门、学生归档及客户归档状态，失效后原Token也不继续访问。学生仍仅取得既有学生身份白名单，不因此新增尚未实现的学生业务接口。

本功能复用现有表、公共JWT和密码能力，没有新增数据库表、没有修改现有MySQL列类型或约束，不使用Dify执行开户，也未修改既有四个企业Workflow。
'''
    usage='''
管理员入口：http://127.0.0.1:8000/admin/accounts 。使用现有平台管理员admin及其当前密码登录；最新本机凭据仍位于Git忽略的.runtime/enterprise-login.json。若从企业登录页使用平台管理员登录，将转到管理员开户页。有效员工身份仍使用/enterprise。

页面提供身份选择、新建／绑定档案、受控职位与部门选项、创建结果、账户分页及管理员接口文档。界面明确显示新账户初始密码123456；不允许其他身份显示开户控件，后端权限校验不依赖界面隐藏。新增测试账户只在外层事务中验证并回滚，当前管理员及原测试业务数据保留；本轮未额外留下测试管理员或正式测试账户。
'''
    api='''
| 方法 | 路径 | 作用 | 权限／文档 |
| --- | --- | --- | --- |
| POST | /api/v1/auth/register | 统一开户及同步档案、默认密码、职位角色 | 平台admin；Idempotency-Key必填；公共OpenAPI隐藏 |
| GET | /api/v1/admin/accounts/options | 四类身份、职位映射、有效部门、默认密码说明 | 平台admin；公共OpenAPI隐藏 |
| GET | /api/v1/admin/accounts | 账户分页，limit=1..100、offset≥0 | 平台admin；不返回password_hash；公共OpenAPI隐藏 |
| GET | /api/v1/admin/openapi.json | 管理员专用OpenAPI | 平台admin；Cache-Control:no-store |

GET /admin/accounts提供登录页面壳；开户控件和账户数据只在平台管理员认证通过后显示。GET /admin重定向到该页面。新增4个管理员／认证HTTP方法与原企业业务75方法分开统计，不覆盖原接口清单。注册参数校验、归档和冲突等业务错误使用{code,message,data}信封；业务码400／403／404／409可随HTTP200返回，认证／身份拒绝使用HTTP401／403。学生、客户和管理员不会被伪装成employee以绕过企业接口权限。
'''
    examples='''
### 管理员开户请求示例（待手动执行，不代表已创建）

先POST /api/v1/auth/login取得管理员Bearer Token，随后为注册请求提供Authorization与Idempotency-Key（如register-manager-demo-001）。初始密码由服务端固定，以下请求不包含密码。

新建主管员工与登录账户：
```json
{
  "identity_type": "employee",
  "username": "demo.manager",
  "profile": {
    "employee_no": "REG_MANAGER_001",
    "full_name": "注册测试主管",
    "department_id": 1,
    "position_title": "部门主管"
  }
}
```

新建学生与登录账户：
```json
{
  "identity_type": "student",
  "username": "demo.student",
  "profile": {
    "student_no": "REG_STUDENT_001",
    "full_name": "注册测试学生",
    "department_id": 1
  }
}
```

绑定已有学生：{"identity_type":"student","username":"demo.student.existing","student_id":2}。学生ID须实际存在、active、未归档且未开户；使用前从数据库确认当前状态，不同时提供profile。

新建客户：{"identity_type":"customer","username":"demo.customer","profile":{"full_name":"注册测试客户","department_id":1}}。

新建平台管理员：{"identity_type":"admin","username":"demo.admin"}。不提供employee_id／student_id／customer_id或profile。

新账户创建成功后可通过现有登录接口使用123456登录。员工role_codes由职位生成；学生及客户本人权限由对应档案ID约束。新建档案的主键使用本次返回值，不预设连续ID；验证事务回滚仍可能产生自增ID间隔。职位、学号、工号、用户名等唯一值已使用时需换新值或正确绑定已有档案。
'''
    architecture='''
### 本次新增／接入路径

```text
app/
  api/common/account_registration.py          管理员注册、选项、账户分页
  schemas/common/account_registration.py      四身份判别联合与新建／绑定校验
  services/common/account_registration.py     档案＋账户＋角色＋审计事务服务
  core/common/admin_authorization.py          仅平台admin身份依赖
  core/common/account_state.py                登录及每次访问校验档案状态
  core/common/position_roles.py               受控职位映射读取
  core/common/admin_openapi.py                独立管理员OpenAPI
  position_roles.yaml                        精确职位→员工业务角色配置
frontend/
  admin/accounts.html                        管理员开户及接口文档入口
  js/admin/accounts.js                       四身份表单、幂等提交与权限展示
  css/admin/accounts.css                     管理员页面与手机布局
tests/enterprise/
  test_account_registration.py               15项开户、权限、事务回归
  admin_registration.browser.js              8项页面回归，拦截API不写真实库
scripts/enterprise/
  check_registration_mysql.py                真实MySQL事务回滚验证
  check_registration_local.py                已部署服务只读HTTP验收
  append_registration_docs.py                六文档快照、只追加及字节前缀验证
```

公共接入调整位于app/main.py、app/api/auth.py所复用的认证服务、app/core/auth.py、app/core/response.py、app/services/auth_service.py、app/access_control.yaml及app/models/user_account.py。UserAccount仅增加SQLite主键类型变体以验证真实自增开户，MySQL仍为BIGINT，不执行DDL。企业员工配置在app/services/enterprise/enterprise_admin.py同步职位与role_codes，保留原公共认证、唯一Base.metadata与业务分包，不复制另一套登录系统。企业前端只增加管理员登录分流。
'''
    checks='''
### 实际验收与运行

- 企业专项回归共35项通过，其中本次新增15项，原20项仍通过；覆盖平台admin／员工admin角色差异、四身份开户、默认密码、已有档案绑定、归档拒绝、唯一冲突、幂等、审计失败整体回滚、职位联动、自身授权变更拒绝、登录后归档撤权及公开文档隐藏。
- 真实本地MySQL完成admin／employee／student／customer开户、123456密码验证、同键回放；另以真实请求依赖完成老师开户和员工越权拒绝。所有新增账户、档案、审计均在外层事务中回滚，未额外留下平台管理员。
- 已部署HTTP检查通过：现有admin登录、公开OpenAPI无注册路由及Schema、受保护OpenAPI可读、职位选项、账户分页无密码、匿名401、页面及资源可用。
- 管理员页面8项浏览器回归通过，覆盖四身份表单、已有学生绑定、失败重试同键、管理员文档、手机布局和员工隐藏入口；使用独立上下文拦截写接口，不冒充真实库写入验证。原编辑弹窗9项浏览器回归仍通过。
- 另外使用真实管理员登录浏览器，核验职位选项、有效部门、账户列表及私有文档加载；没有在浏览器创建额外持久账户。当前现有管理员密码保持用户上次指定值。

```powershell
python -X utf8 -W ignore::DeprecationWarning -m unittest discover -s tests/enterprise -v
python -X utf8 scripts/enterprise/check_registration_mysql.py
python -X utf8 scripts/enterprise/check_registration_local.py
python -X utf8 scripts/enterprise/append_registration_docs.py
```

真实MySQL验收脚本创建的账户最终回滚，不能拿其返回ID当正式登录账户。部署后端已重启加载新接口；Dify及原业务资料保留。源码与页面完成Python编译和JS语法检查。六份指定文档的实施前副本、长度和SHA256在.runtime/registration-doc-originals中，最终以原始字节前缀校验确认原文未被改写。
'''
    content={
        '操作文档.md':common+api+examples,
        '企业管理模块_本地实施方案.md':common+usage+architecture+checks,
        '企业管理模块_接口测试数据.md':usage+examples+checks,
        '企业管理模块_接口清单.md':common+api+examples,
        '企业管理模块_实施记录.md':common+usage+api+checks,
        '项目目录架构_最终汇总.md':usage+architecture+api,
    }
    verify()
    for name,body in content.items():
        target=BASE_DIR/'开发文档'/name
        original=(FOLDER/name).read_bytes()
        suffix=target.read_bytes()[len(original):].decode('utf-8')
        if MARKER in suffix:continue
        with target.open('ab') as handle:handle.write(('\n\n'+MARKER+'\n'+body.rstrip()+'\n').encode('utf-8'))
    verify()
    print(json.dumps({'append_only_files':FILES,'marker':MARKER},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--snapshot',action='store_true');parser.add_argument('--append',action='store_true');args=parser.parse_args()
    if args.snapshot:snapshot()
    elif args.append:append()
    else:verify()
