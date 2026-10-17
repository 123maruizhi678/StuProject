# 前端模块与接入说明

本目录已合并下载目录的前端与项目原有公共入口、学生多页面版本。使用原生 HTML、CSS、JavaScript ES Modules，无 npm 构建步骤。下载目录保持原样。

## 启动与入口

在项目根目录运行：

```powershell
conda run -n SST python -m uvicorn app.main:app --reload
```

通过 `http://127.0.0.1:8000/` 进入统一权限工作台。`/login` 是统一登录页，`/account` 查看本人权限，`/health` 返回服务状态。业务页面均在 `/static/` 下，不支持直接双击 HTML。

## 模块划分

| 模块 | 主页面 | 脚本 / 样式 | 当前接入范围 |
| --- | --- | --- | --- |
| 公共入口 | `index.html`、`common/login.html` | `js/common/`、`css/common/style.css` | 登录、会话、权限导航、iframe 装载 |
| 客服 Agent | `agent/agent.html` | `js/agent/`、`css/agent/` | 对话、活动与报名、课程、FAQ；后端六接口已挂载 |
| 客户研判 | `customer/customer.html` | `js/customer/`、`css/common/business.css` | 文本/文件研判、画像规则、记录页面；服务待联调 |
| 企业智能助手 | `enterprise/enterprise.html` | `js/enterprise/`、`css/common/business.css` | 客户、日报、NL2SQL、指令、组织、新人指引、成绩、投诉页面；服务待联调 |
| 学生智能助手 | `student/student-assistant.html` | `js/student/`、`css/student/student.css` | 保留新加入的学生多页面；服务待联调 |
| 智能报告 | `report/report.html` | `js/report/`、`css/report/` | 列表、详情、异步生成、配置；后端五接口已挂载 |
| 数据看板 | `dashboard/dashboard.html` | `js/dashboard/`、`css/common/business.css` | 指标、客户趋势、工单图表页面；服务待联调 |

统一登记文件为 `js/common/modules.js`。`delivered` 表示页面已交付，`apiReady` 表示当前后端接口已对接，两者分别维护。已授权但接口未就绪的模块显示“待联调”，保留子页面与标签浏览、禁用业务表单，并在请求层阻止历史接口调用；不生成虚构业务数据。

当前后端只装配客服、报告和公共认证接口。学生完整服务路由尚未合入；旧请假路由也因客户端缺失而暂未挂载。不要仅修改 `apiReady` 就声称完成接口联调，须先核对真实路由、字段、身份及动作权限。

客户研判目前未配置 `customer_research` 的公共页面/模块权限，因此工作台保持未授权；本轮没有新增或放宽角色权限。报告前端遵循公共接口返回的动作集合，部门主管角色还需后端将其报告权限同步到公共访问清单，前端不按员工身份猜测授权。

## 学生页面

`STUDENT_PAGES` 与模块登记共同维护在 `js/common/modules.js`；`js/common/student-shell.js` 复用此清单提供学生侧导航、图标和对话框。

| 页面 | 功能 |
| --- | --- |
| `student/student-assistant.html` | 学习工作台与服务入口 |
| `student/chat.html` | 智能咨询、办理预览与再次确认 |
| `student/academics.html` | 课程、成绩、考试与截止日期 |
| `student/leave.html` | 请假申请、查询与撤回 |
| `student/tickets.html` | 投诉建议、沟通、确认与评价 |
| `student/reminders.html` | 学业提醒与取消 |
| `student/progress.html` | 文书、院校与签证进度 |
| `student/care.html` | 情绪辅助记录 |
| `student/notifications.html` | 站内通知与已读状态 |
| `student/preview.html` | 下载目录原学生界面，供核对旧功能与字段，不作为正式入口 |

新学生界面作为主入口，下载目录旧实现拆入 `js/student/student.js` 并由 `student/preview.html` 保留。旧页面里的固定学生名单已移除，等待真实本人身份和授权名单；不以写死 ID 模拟真实学生。

兼容入口：`/student-assistant` 返回学生主页面；`student/login.html` 转到统一登录；`enterprise/index.html`、`research/index.html`、`report/index.html` 分别转到各自正式模块页。原重复的 `js/system.js`、`js/portal.js`、`css/system.css` 已整合到公共导航、学生样式与入口转接脚本。

## 公共请求与身份

- 所有模块复用 `js/common/api.js`，统一处理 HTTP 状态、`code/message/data` 信封、超时、401 和 403，支持 JSON、FormData 与幂等请求头。
- 统一登录只向 `/api/v1/auth/login` 提交用户名密码，使用 `/auth/me/access` 获取真实权限；访客清单来自 `/auth/public-access`。
- Token 和有效期仅存储于同源 `sessionStorage`；`tokenStore` 是对同一会话的兼容读取，不建立第二套认证。
- 报告已移除 `report-token` / `report-me` 本地缓存及独立登录表单；旧本地缓存不会再被读取。
- 同标签页工作台与 iframe 通过公共身份事件同步退出和失效；接口权限始终由后端逐接口校验。
- 报告失败重试及学生办理适配器保留相同内容的幂等键；结果未确认时不自动重发。
- 报告时间输入明确按北京时间 `+08:00` 提交，不受浏览器本地时区影响。

## 共享资源与维护

`css/common/business.css` 保留下载版本的独立业务页面视觉组件；仅由对应业务文档加载，不覆盖公共工作台或学生样式。`js/common/charts.js` 是共享 SVG 图表库，`effects.js` 是可选动效，`ui.js` 是旧业务页面通用 DOM 组件。各业务样式均通过独立 iframe 文档隔离。

新增模块功能应放在自身 `js/<module>/`、`css/<module>/` 和页面目录；不要再次集中到公共 `app.js`。旧单页内的重复客服/报告实现由独立模块取代，旧 `/meta` 探测和重复顶层 API 客户端不再加载。

### 智能报告模块合并（2026-10-17）

已将 `C:\Users\马睿智\Downloads\frontend1\frontend` 中的智能报告三件套按模块合并：页面位于 `report/report.html`，样式位于 `css/report/report.css`，页面逻辑位于 `js/report/report.js`，接口适配继续使用 `js/report/report-api.js`。合入新版科技风布局、背景动效、深浅主题、列表等宽字段和详情报告代码；保留列表筛选/分页、异步生成、指标/正文阅读及配置编辑。

登录与权限继续复用公共会话和后端动作清单，未引入下载版本的独立令牌缓存或 API 基址覆盖。生成失败重试继续复用幂等键，时间仍按北京时间提交。模块登记和 `report/index.html` 兼容入口沿用现有配置；下载源文件保持原样。本项目为原生静态前端，无 npm 构建步骤。

本次合并验证：报告脚本语法检查通过；现有 Node 前端契约测试通过 13/14 项，未通过项为企业模块 `apiReady: false` 与测试中预期允许企业接口请求的既有不一致，涉及的公共模块文件未改动。Edge 隔离浏览器回归通过，新增覆盖报告详情/指标/正文转义、带版本号的配置保存、反向时间窗阻止提交、深浅主题和 390px 报告布局，并保留生成失败重试、统一登录与其他模块回归。浏览器使用虚构接口响应，未调用真实数据库或 Dify。

## 验证

```powershell
node --test tests/common/test_frontend.mjs
python -B -m unittest discover -s tests/common -p "test_*.py"
```

前端回归覆盖统一认证、权限与返回地址、模块入口与静态依赖、公共上传请求、报告幂等重试和北京时间转换。浏览器联调使用虚构接口响应，不写真实数据库、不调用真实 Dify；这与真实业务环境端到端验收分别记录。

本次整合验证：39 项公共 Python 回归、14 项前端契约回归、32 个 JavaScript 文件语法检查通过；本地 Edge 浏览器隔离联调覆盖公开客服、报告登录和重试、模块权限、业务标签切换、学生服务页面、旧入口跳转及 390px 手机布局。浏览器回归脚本为 `tests/common/test_frontend_browser.mjs`，可通过 `PLAYWRIGHT_MODULE` 和 `BROWSER_EXECUTABLE` 指定本机已有的 Playwright 与浏览器。
