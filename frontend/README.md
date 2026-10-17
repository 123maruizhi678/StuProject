# 公共登录与权限入口及各组页面接入方案

本前端使用原生 HTML、CSS、JavaScript，无 npm 构建步骤。公共入口采用深色科技风、青绿色强调色、侧栏导航和响应式卡片布局。当前只实现公共登录与权限入口；业务模块由各组员独立开发页面。

## 访问与目录

在项目根目录启动：

```powershell
conda run -n SST python -m uvicorn app.main:app --reload
```

- `http://127.0.0.1:8000/`：主页面和业务模块目录。
- `http://127.0.0.1:8000/login`：独立统一登录页面。
- `http://127.0.0.1:8000/account`：当前身份和访问权限。
- `http://127.0.0.1:8000/health`：JSON 服务状态。

通过 FastAPI 访问页面，不直接双击 HTML，以便同源请求公共接口并加载 `/static` 资源。主入口和登录页本身可公开访问，敏感数据与操作仍由后端逐接口鉴权。

```text
frontend/
  index.html                  主页面、业务入口和权限视图
  common/login.html           独立登录页
  css/common/style.css        公共科技风样式与移动端适配
  js/common/
    api.js                    公共请求、会话与错误处理
    modules.js                五个业务模块的入口登记
    app.js                    主入口、权限导航与页面装载
    login.js                  登录交互
  agent/                      客服组交付目录
  customer/                   客户研判组交付目录
  enterprise/                 企业助手组交付目录
  student/                    学生助手组交付目录
  report/                     智能报告组交付目录
```

业务页面目录按实际交付创建，当前没有创建空壳业务页面。已移除原主页面混合的业务实现、虚构业务数据、图表脚本、旧背景效果及旧报告前端，后端报告接口保留。

## 公共功能与三个接口

| 接口 | 页面用途 |
| --- | --- |
| `GET /api/v1/auth/public-access` | 未登录时取得公开页面与模块清单 |
| `POST /api/v1/auth/login` | 提交账号密码，取得 access_token、token_type、expires_in |
| `GET /api/v1/auth/me/access` | 携带 Bearer JWT，取得本人身份、权限、页面与模块 |

成功响应读取 `code/message/data`。公共登录失败可能为实际 HTTP 401/403/422；业务接口也可能采用 HTTP 200 + 业务 code。`api.js` 同时处理两种错误约定，401 清除会话，403 显示拒绝提示，断网或超时提供可重试提示。

Token 及有效期保存在同源 `sessionStorage`，不保存密码，不保存 Dify Key。退出只清除浏览器会话；当前后端没有注销或服务端撤销 Token 接口，不宣称退出会吊销已签发的 JWT。

前端可见性依据后台清单；浏览器显示菜单不代表获得接口权限。公共认证采用账号实际 identity_type 映射 YAML 权限，报告主管等业务附加角色应由负责模块与公共权限清单协调接入，前端不会猜测或自行授予业务权限。

## 组内页面接入

| 模块 | 页面文件 | 样式/脚本目录 | 当前匹配的页面或模块标识 |
| --- | --- | --- | --- |
| 客服 Agent | `agent/agent.html` | `css/agent/`、`js/agent/` | agent / agent_center，公开访问 |
| 客户研判 | `customer/customer.html` | `css/customer/`、`js/customer/` | customer_research，尚需负责人与公共权限策略对齐 |
| 企业智能助手 | `enterprise/enterprise.html` | `css/enterprise/`、`js/enterprise/` | employee_dashboard / employee_workspace |
| 学生智能助手 | `student/student-assistant.html` | `css/student/`、`js/student/` | student_dashboard / student_workspace |
| 智能报告 | `report/report.html` | `css/report/`、`js/report/` | report / report_center |

1. 各组实现自己的 HTML、CSS、JavaScript，不再把业务代码塞入公共 `app.js`。
2. 页面复用 `/static/css/common/style.css` 的颜色变量及基础组件；模块样式使用独立类名或页面根节点限定作用域。
3. 请求复用 `/static/js/common/api.js`，业务路径为相对于 `/api/v1` 的路径：

   ```html
   <link rel="stylesheet" href="/static/css/common/style.css">
   <script type="module">
     import { request } from "/static/js/common/api.js";
     // 由业务组使用自己已实现的接口，例如 request("/report/configs")。
   </script>
   ```

4. 在 `app/access_control.yaml` 确认页面/模块标识及角色权限。公共登记不会替业务接口授予权限，更不会自动创建业务路由。
5. 在 `js/common/modules.js` 确认 entry、pageIds/moduleIds，并在页面实际交付后设置 `delivered: true`。当前五个模块都保持未交付状态，已授权但未交付的模块显示“待接入”；未授权模块显示“未授权”或“需登录”。
6. 主页面先校验授权和本地页面地址，再在同源 iframe 中加载独立业务页面，也支持独立窗口。各组可以单独访问页面调试；业务接口依旧必须校验身份、动作及数据范围。

公共文件由公共模块负责人维护，各业务负责人只修改自己的目录及约定的入口登记。客户研判等尚未配置的权限不能由前端临时放开。

## 本轮后端配套

- 登录 API、JWT 认证、权限、Dify HTTP 工具、认证服务、登录 Schema 与账号模型迁入各层 common 包；调用方已同步改为新导入路径。
- `app/repositories/common/account_repository.py` 提供按用户名和 ID 查询；认证回查会刷新账号状态。
- `app/models/common` 整理现有 SQL 定义的12张共享表，使用唯一 `app.database.Base.metadata`；不自动建表或修改真实数据库。
- `notification_repository.py`、`operation_log_repository.py` 与业务使用同一个 Session，不自行提交事务；学生请假已复用两者。通知仓储负责入队及已发布站内通知的本人读取，不启动投递任务；审计按真实操作者和幂等键存储回执。
- 电话保护、通用日志脱敏功能本轮按要求暂不实施。现有日志生成工具保留，现有数据库密文字段仍按表结构映射。
- 当前学生请假 Dify 适配器缺失，因此其 HTTP 路由仍暂未挂载；本轮请假联合测试使用虚构 Workflow。未恢复或部署其他业务模块及 Dify 应用。

## 验证

```powershell
# 项目 Python 环境即可运行，不要求额外安装 pytest
python -B -m unittest discover -s tests/common -p "test_*.py"
# 原生 JavaScript 契约回归，无 npm 依赖
node --test tests/common/test_frontend.mjs
```

隔离测试只使用虚构账号、SQLite 内存库和虚构 Workflow。真实浏览器检查覆盖错误密码、登录/权限同步、退出、401失效、断网、非法跳转和桌面/手机布局。实际业务环境仍需使用已存在的统一账号登录；测试账号不会写入真实数据库。

本轮验证结果：公共 Python 回归39项、前端 JavaScript 回归8项、真实浏览器检查11项全部通过；浏览器检查还验证了已登记独立页面在主入口中的装载。没有执行真实 Dify 调用或改写真实数据库。
