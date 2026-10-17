# 企业管理前端与小组集成说明

采用原生 HTML、CSS 和 JavaScript ES Modules，无需 npm、打包工具或外部 CDN。

## 运行与入口

后端运行后，在浏览器通过 HTTP 访问：

- 系统主页面：`http://127.0.0.1:8000/static/index.html`
- 企业管理入口：`http://127.0.0.1:8000/enterprise`
- 业务页面直达示例：`http://127.0.0.1:8000/enterprise#/scores`
- 平台管理员账户管理：`http://127.0.0.1:8000/admin/accounts`

不能直接双击 HTML 以 file:// 打开，模块导入和接口调用需要同源 HTTP 服务。现有后端 `/` 保留服务状态响应，未改变其协议。

使用有效员工或最高管理员账号登录企业工作台。平台admin与员工角色admin均为最高管理员，可以直接使用全部企业功能，并通过“账户管理”入口开户；普通员工仍按职位和数据关系授权。新开账户初始密码仍为123456，现有管理员密码不变。页面不预置演示账号、密码或业务数据。

## 主页面如何调用模块

系统主页面中的企业入口直接链接 `/enterprise`。小组主页面可以复用：

```html
<a href="/enterprise">企业管理</a>
```

企业管理自己的导航壳 `enterprise.html` 通过同源 iframe 加载独立业务 HTML，侧栏和顶栏保持稳定。业务页面与主页面没有共享的 DOM 或全局变量，离开页面后详情、表单和助手预览会一起卸载。浏览器前进、后退及带 hash 的直达地址均可使用。

如组内主页面已有 iframe 容器，也可加载 `/enterprise`。需要主页面及接口保持同源，或由小组统一设置反向代理；不要在 URL 中传递 Token。

## 文件分工

```text
frontend/
  index.html                         小组原主页面，企业入口链接独立模块
  js/app.js                          移除重复企业演示逻辑，保留模块入口及其他已有模块
  enterprise/
    enterprise.html                  企业登录、侧栏、顶栏与页面容器
    pages/
      overview.html                  工作概览
      assistant.html                 智能助手
      customer.html                  客户管理
      daily-report.html              员工日报
      ...                            其他业务独立HTML，见下表
  js/enterprise/
    enterprise.js                    入口认证、权限导航、hash路由、iframe消息处理
    api.js                           JWT、响应信封、幂等请求、身份与权限校验
    catalog.js                       各业务接口路径、字段、动作权限、中文标签与枚举
    resource.js                      列表、分页、详情、表单、业务操作公共控制器
    overview.js                      可见数据统计、常用功能、待办及通知
    assistant.js                     指令预览/确认、自然语言查询、制度问答及语音
    ui.js                            北京时间展示、页面说明
    icons.js                         本地SVG图标
  css/enterprise/enterprise.css      科技风公共样式、组件及响应式布局
  admin/accounts.html               独立的平台管理员开户页面
  js/admin/accounts.js              管理员开户逻辑
  css/admin/accounts.css            复用企业公共主题，添加开户页面布局
```

## 业务页面和接口

以下路径均位于 `pages/`，企业业务 API 前缀均为 `/api/v1/enterprise`。界面上的操作还会检查具体动作权限，后端负责最终的身份、数据范围及对象权限判断。

| 独立页面 | 对接接口及主要功能 |
| --- | --- |
| overview.html | 按权限查询客户、学生、日报、工单总数；待办、通知及快捷入口 |
| assistant.html | POST /command、/command/confirm、/nl2sql、/onboarding/ask、/voice/transcribe |
| todos.html | GET /todos；查看待办信息，未模拟尚未接入的学生请假审批 |
| customer.html | /customer 列表、新建、详情、更新、归档；状态、转派、电话查重、跟进历史、新增跟进及调整计划 |
| daily-report.html | /daily-report 列表、新建、详情、更正、作废；POST /daily-report/summary |
| students.html | GET /students 及 /students/{id}；只读学生档案 |
| courses.html | /courses 列表、新建、详情、更新课程名称与状态 |
| student-courses.html | /student-courses 列表、新建、详情、更新选课状态 |
| scores.html | /scores 列表、新建、详情、更正、作废 |
| academic-events.html | /academic-events 列表、新建、详情及变更节点 |
| application-progress.html | /application-progress 列表、新建、详情及进度更新 |
| tickets.html | /tickets 列表、详情、分派、人工回应及给出方案 |
| knowledge.html | /knowledge 列表、新建、详情、编辑、停用及审核发布 |
| notifications.html | /notifications 列表、详情及标记已读 |
| employees.html | /employees 列表、新建员工档案、详情、更新与角色配置；账户开通仍使用管理员页 |
| departments.html | GET /organization；/departments 新建、更新及停用 |
| student-bindings.html | /student-bindings 列表、新建、更新及停用 |
| operation-logs.html | GET /operation-logs；只读操作审计 |

管理员页保持现有管理员专用接口：POST `/api/v1/auth/register`，GET `/api/v1/admin/accounts/options`、`/api/v1/admin/accounts`、`/api/v1/admin/openapi.json`。平台admin与员工角色admin均可使用，普通员工不显示开户入口。`/auth/me/access`及`/enterprise/me/permissions`的`is_admin`表示最高管理员；账号原始身份仍由identity_type返回。

## 协作约定

1. 修改业务标题、表格列、创建/编辑字段及权限时，更新 `catalog.js` 中对应资源；不修改其他业务定义。
2. 独立页面通过 body 的 `data-resource` 关联配置，例如成绩页使用 `data-resource="scores"`。公共控制器负责列表及表单交互。需要定制业务布局时，在自己的 HTML 中挂载自己的 ES Module，并复用 `api.js`、`ui.js` 与公共 CSS。
3. 新增页面时将页面键加入 `enterprise.js` 对应导航分组。页面间跳转使用 `api.js` 的 `navigate(key)`；容器检查消息来源及目标权限。
4. 接口采用 `{code,message,data}` 信封。HTTP200 仍可能携带业务错误；不得只根据 HTTP 状态判定成功。Token 仅保存在当前标签页的 sessionStorage 中，使用 Authorization Bearer 发送。
5. 写操作携带 Idempotency-Key，同参数失败重试沿用原键，成功后释放；更新携带 expected_version，学业节点使用 expected_event_version。冲突显示接口提示并保留表单。
6. 时间输入统一采用北京时间，提交包含 `+08:00`；后端无偏移时间戳按 UTC 转为北京时间展示。日期字段保留原日期。
7. 搜索框明确为“筛选本页记录”，不伪装成全库检索。分页使用实际 limit/offset，总数使用接口 total；组织部门为数组接口时在前端分页。
8. 动态文本使用 textContent 创建；不把模型输出、客户姓名等未经处理的数据插入 innerHTML。助手写入必须先预览、再确认。

## 清理范围与校验

已移除旧 `js/app.js` 中重复的企业演示页面及不匹配的企业接口调用；其他模块已有前端继续保留，便于组员分别维护。企业页面不加载旧主页面的 app.js、charts.js、effects.js 或全局 API 对象。

浏览器检查使用独立上下文拦截 API，不向业务数据库写测试数据：

- `tests/enterprise/enterprise_editor.browser.js`：编辑回填、保存参数、版本、失败提示及跨页面详情清理。
- `tests/enterprise/enterprise_modules.browser.js`：18个页面、分页、权限、助手及手机布局。
- `tests/enterprise/admin_registration.browser.js`：四类开户表单、默认密码约定、重试及管理员权限。

这些文件是 Playwright MCP 的可执行 async 函数，可通过 browser_run_code_unsafe 的 filename 参数加载；不是需要 npm 安装的 Playwright Test 测试套件。
