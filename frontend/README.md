# 前端页面与协作约定

原生 HTML + CSS + JavaScript ES Modules，无 npm 安装或打包步骤。
从项目根目录启动 `python scripts/student/run_student_app.py --port 8010`，浏览器访问 `http://127.0.0.1:8010/`。
须经 HTTP 服务访问，不支持直接双击 HTML（页面使用统一 `/static/` 资源路径及同源 API）。

## 分工入口

| 模块 | 独立页面 | 业务脚本 | 当前范围 |
|---|---|---|---|
| 系统总览 | `index.html` | `js/portal.js` | 模块导航 |
| 学生智能助手 | `student/student-assistant.html`，服务地址 `/student-assistant` | `js/student/` | 本次完整实现的模块 |
| 企业管理 | `enterprise/index.html` | 目前由 `js/portal.js` 提供接入页 | 对应成员继续实现业务 |
| 客户研判 | `research/index.html` | 目前由 `js/portal.js` 提供接入页 | 对应成员继续实现业务 |
| 智能报告 | `report/index.html` | 目前由 `js/portal.js` 提供接入页 | 对应成员继续实现业务 |

各模块保留独立目录。其他成员开发时，为其页面指定独立 JS 文件，复用 `css/system.css` 的样式和 `js/system.js` 的导航、图标、对话框等组件即可。
不要把其他模块的业务逻辑加入 `js/student/`，也不要在学生目录中新增共享后端模型。
模块接入页标注“服务准备中”，没有伪造的办理按钮、业绩数据或接口。

## 学生模块页面与接口

| 页面 / 独立业务脚本 | 功能 | 接口（均在 `/api/v1` 下） |
|---|---|---|
| `student/login.html` / `login.js` | 登录、回到目标页面 | `POST /auth/login`、`GET /auth/me/access` |
| `student/student-assistant.html` / `overview.js` | 学生工作台、真实业务计数、近期学业节点 | 课程、请假、提醒、通知、学业查询 |
| `student/chat.html` / `chat.js` | 智能咨询、本人查询、办理预览与再次确认 | `POST /student/chat`、`POST /student/actions/confirm` |
| `student/academics.html` / `academics.js` | 课程、成绩、考试/截止日期，设置提醒 | `GET /student/courses`、`/scores`、`/academic`，`POST /student/reminders` |
| `student/leave.html` / `leave.js` | 提交、按审批状态筛选、撤回请假 | `GET/POST /student/leave`、`DELETE /student/leave/{apply_id}` |
| `student/tickets.html` / `tickets.js` | 投诉建议、详情、分页沟通、补充、确认、重开、评价 | `/student/complaint`、`/student/tickets` 及详情、records、reply、confirm、rating |
| `student/reminders.html` / `reminders.js` | 提醒列表与取消 | `GET /student/reminders`、`DELETE /student/reminders/{id}` |
| `student/progress.html` / `progress.js` | 申请阶段、来源更新时间 | `GET /student/progress` |
| `student/care.html` / `care.js` | 情绪辅助记录与支持提示 | `POST /student/mental/monitor` |
| `student/notifications.html` / `notifications.js` | 全部/已读/未读、详情和标记已读 | `/student/notifications` 及详情、read |

`student-assistant.js` 仅负责学生页面装配，`ui.js` 负责列表分页、状态、表单和确认对话框，`api.js` 负责统一信封、Bearer 和幂等键。
每个 HTML 可单独进入；学生侧统一导航由 `system.js` 的 `studentPages` 声明，系统模块由 `modules` 声明。

## 接口与数据规则

- 复用 `js/common/api.js` 导出的 tokenStore，保持与公共登录同一 sessionStorage 凭据；没有在前端存储 Dify Key、数据库凭据或签名密钥。
- 学生请求读取 HTTP 状态和业务 code，展示受控的业务错误信息，401 时清除过期凭据。
- 写操作自动携带 Idempotency-Key。未确认结果的失败保留原请求键，相同内容重试不换键；成功后才清除。
- 所有撤回、确认、补充、评价、提醒设置/取消携带接口要求的版本或更新时间，页面不指定学生身份。
- 设置提醒时读取全部分页提醒，核对已有设置的更新时间，避免只看前100条造成冲突。
- 数据源错误展示错误状态，空数据展示空状态，未登录展示登录提示；无默认业务假数据或本地伪造的“办理成功”。
- 进度页只高亮当前记录所属阶段，不推断其他阶段已完成。
- 聊天中的申请/工单先显示完整参数，学生确认后才调用确认接口。取消不调用办理接口；未知结果不自动重发。
- 系统与模块页面同源部署。拆分部署前需要后端允许相应来源、Idempotency-Key、PUT、DELETE。

## 清理与保留

旧的单页学生界面和其脚本已重写，旧学生样式文件已移除。系统首页改为模块总览。
公共 `common/`、`css/common/`、`js/common/` 的原有登录页面和代码保留，没有修改，便于组长继续维护。
旧 `/login`、`/account` 仍使用公共页面；新版页面的登录入口指向独立的科技风登录页，使用相同后端认证。

验证范围应分别记录：静态导航/响应式、真实隔离库的页面联调、真实环境端到端。后端数据或凭据未就绪时，不代表前端已经完成真实库业务验收。

## 本次验证与交付边界

- JavaScript 语法/导入、HTML 资源路径、桌面及移动布局已检查；后端测试 112 项通过。
- 页面操作已在隔离 SQLite 测试库联调，覆盖登录、请假提交/撤回、工单确认、提醒设置/取消、通知已读及聊天办理确认。
- 隔离预览使用模型替身，未调用真实 Dify；重复欢迎语属于测试模型行为，不能用于验收真实助手的意图识别与请假多轮对话。
- 真实环境仍需配置有效的认证密钥、数据库及业务数据源，并验证真实 Dify 对话和办理全流程。
- 测试账号、隔离测试服务、截图、环境文件及公共 common 代码不包含在本次前端提交中。
