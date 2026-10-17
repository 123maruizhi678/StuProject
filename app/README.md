# 公共基础能力后端

唯一入口为 app.main:app；配置仅由 app/config.py 读取项目根目录 .env。Base、engine 和请求级会话仅在 app/database.py 定义。启动时不执行建表。

```text
app/
  api/common/auth.py                    三个认证HTTP接口
  core/common/auth.py                   当前JWT账号依赖
  core/common/authorization.py          策略、精确权限与访问清单
  core/common/response.py               统一信封和异常出口
  core/common/logger.py                 日志与敏感字段脱敏
  core/common/dify.py                   同步/异步HTTP传输
  schemas/common/auth.py                公共请求与响应
  services/common/auth_service.py       密码和JWT
  services/common/account_service.py    受控账号开通及同事务审计
  repositories/common/account_repository.py  账号/有效主档查询
  models/common/                        六张必要共享表唯一映射
  access_control.yaml                   四种身份与八种员工角色的策略
  main.py / config.py / database.py     唯一公共入口
```

## 接口

- POST /api/v1/auth/login：JSON username、password；返回 access_token、token_type、expires_in。
- GET /api/v1/auth/public-access：匿名访问，仅公开页面与模块元数据。
- GET /api/v1/auth/me/access：公共 Bearer JWT，仅本人身份、角色、权限、页面和模块。

公共认证成功使用 HTTP200 和 code=0；失败使用实际 HTTP400/401/403/500/503，同时保留 code、message、data 信封。400输入错误不回显密码；401包含 WWW-Authenticate: Bearer。

## 业务模块接入

```python
from fastapi import Depends
from app.core.common.authorization import require_permission

@router.get("/protected")
def protected(account=Depends(require_permission("report.read"))):
    # 此处还必须按当前动作校验对象、部门或学生关系。
    ...
```

get_current_account 逐请求解析 JWT.sub，读取真实 user_account，再核对有效主档和员工主部门。account.access_context 提供服务器取得的 employee_id、student_id、department_id 和 role_codes。不能以 user_id 代替 employee_id。

平台管理员、员工管理员和部门主管严格区分；平台管理员不自动取得所有业务动作。公共权限仅声明动作，列表/详情/写入/回放的数据范围仍由各业务固定服务独立校验。公共模块不注册这些业务接口。

通用 Dify 工具由后端调用者传入 api_base、api_key 和 payload，不发布面向浏览器的模型接口，不解释工作流结果，也不执行模型 SQL。

账号初始化和运行步骤见项目根 README；完整实现与验证见开发文档/公共登录与权限入口_开发说明.md。
