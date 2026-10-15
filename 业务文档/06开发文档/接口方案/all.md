# 接口与身份权限总览（合并版）

> **合并来源**
> - `客服Agent/客服Agent接口与身份权限清单.md`
> - `企业管理/企业管理模块_接口与角色权限_抽取.md`
>
> **组织方式**：按模块分章节（模块一、模块二），每个模块统一采用「接口清单 → 身份/角色清单 → 权限映射 → 总览」结构，便于跨模块对照。

---

# 模块一：客服Agent

> **来源**：客服Agent接口与身份权限清单
> **范围**：客服Agent 模块，共 6 个接口。
> **鉴权现状**：当前接口均**无鉴权（匿名直连）**；下表为「现状 / 目标态」对照。目标态防护重点为「限流 + 防刷 + 敏感数据脱敏」。

## 1.1 接口清单

| 序号 | 方法 | 路径 | 说明 | 访问级别（目标态） |
| --- | --- | --- | --- | --- |
| 1 | POST | `/api/v1/agent/chat` | 客服对话（含会话/消息落库） | public |
| 2 | GET | `/api/v1/agent/events` | 活动列表 | public |
| 3 | GET | `/api/v1/agent/events/{id}` | 活动详情 | public |
| 4 | POST | `/api/v1/agent/events/signup` | 活动报名（写库 + 采集手机号） | public（可升级 visitor） |
| 5 | GET | `/api/v1/agent/courses` | 课程列表 | public |
| 6 | GET | `/api/v1/agent/faq` | FAQ 兜底查询 | public |

## 1.2 身份清单

| 身份 | type | role | 来源 | 主要使用模块 |
| --- | --- | --- | --- | --- |
| 员工 | `employee` | `advisor` | 企业登录后签发 | 企业智能助手、智能报告、后台管理 |
| 学生 | `student` | `student` | 学生登录后签发 | 学生智能助手 |
| 访客/潜在客户 | `visitor` | `anonymous` | 匿名或留资（首访后端签发匿名 token） | **客服Agent** |

> **认证机制**：统一采用 **JWT（Bearer Token）**，`Authorization: Bearer <token>` 传递，token 内含 `type` / `role` / `scopes` 字段。

## 1.3 身份 × 接口 权限矩阵

> **说明**：客服Agent 在统一鉴权中为 **`public` 级别（公开访问，不强制身份认证）**。因此从「能否访问」角度，**任何身份均可访问全部 6 个接口（无需登录）**；但从「业务目标与授权 scope」角度，各身份的归属不同。

| 接口 | 访客/潜在客户（visitor） | 员工（employee） | 学生（student） |
| --- | --- | --- | --- |
| POST `/agent/chat` | ✅ 主用（`agent:chat`） | ✅ 可访问（public） | ✅ 可访问（public） |
| GET `/agent/events` | ✅ 主用（`agent:events`） | ✅ 可访问（public） | ✅ 可访问（public） |
| GET `/agent/events/{id}` | ✅ 主用（`agent:events:read`） | ✅ 可访问（public） | ✅ 可访问（public） |
| POST `/agent/events/signup` | ✅ 主用（`agent:signup`，强限流 + 防重） | ✅ 可访问（public） | ✅ 可访问（public） |
| GET `/agent/courses` | ✅ 主用（`agent:courses`） | ✅ 可访问（public） | ✅ 可访问（public） |
| GET `/agent/faq` | ✅ 主用（`agent:faq`） | ✅ 可访问（public） | ✅ 可访问（public） |

### 1.3.1 访客/潜在客户（visitor）

- **归属模块**：客服Agent（本模块目标用户）。
- **持有 scope**：`agent:*`（覆盖全部 6 个接口）。
- **可调用接口**：全部 6 个。
- **认证**：不强制登录；首访由后端签发匿名 `visitor` token，绑定 `session_id`，用于会话关联、限流计数与防刷审计。
- **特殊约束**：`signup` 接口风险最高，即使访客匿名访问也须接受「IP 限流 + 幂等（event_id + customer_phone 唯一约束）+ 手机号格式校验 +（可选）验证码」。

### 1.3.2 员工（employee）

- **归属模块**：企业智能助手、智能报告、后台管理（非客服Agent）。
- **持有 scope**：以 `enterprise:*` 为主（企业模块授权）。
- **可调用接口**：因客服Agent 为 `public`，员工身份**技术上可访问全部 6 个接口**，但**非业务目标用户**；其主用接口不在本清单内。
- **认证**：登录后签发含真实身份的 JWT（authenticated 级别）。

### 1.3.3 学生（student）

- **归属模块**：学生智能助手（非客服Agent）。
- **持有 scope**：以 `student:*` 为主（学生模块授权）。
- **可调用接口**：因客服Agent 为 `public`，学生身份**技术上可访问全部 6 个接口**，但**非业务目标用户**；其主用接口不在本清单内。
- **认证**：登录后签发含真实身份的 JWT（authenticated 级别）。

---

# 模块二：企业管理

> **来源**：企业管理模块_接口与角色权限_抽取（抽取自 `企业管理模块_接口方案_待确认.md`，版本 V1.1，2026-10-15，状态：方案评审）。
> **范围**：企业管理模块，含第 5 节业务接口与第 6 节管理配套接口。
> **路径约定**：所有接口路径均省略基础前缀 `/api/v1/enterprise`。P0 为基础业务与跨端闭环，P1 为智能能力；接口均为拟定，未实现。
> **鉴权现状**：按第 12 节分配六个固定角色，权限为后端固定配置；未列入默认或条件授权的接口一律不开放。

## 2.1 接口清单

### 2.1.1 企业端业务接口（第 5 节）

#### 当前员工与通讯录（P0）

| 编号 | 方法 | 路径 | 功能重点 |
| --- | --- | --- | --- |
| ORG-01 | GET | `/me` | 返回本人 employee_id/full_name/department_id/role_codes 及受控功能列表 |
| ORG-02 | GET | `/departments` | 部门职能、主管及组织树，不暴露后台身份字段 |
| ORG-03 | GET | `/employees` | 按关键词/部门/岗位返回有效员工通讯录 |
| ORG-04 | GET | `/employees/{employee_id}` | 授权工作资料和工作联系方式，不返回密文 |

#### 客户与跟进（P0）

| 编号 | 方法 | 路径 | 功能重点 |
| --- | --- | --- | --- |
| CUS-01 | POST | `/customer` | 创建客户，归属按身份或授权分派确定 |
| CUS-02 | GET | `/customer` | 按条件筛选客户，默认排除归档 |
| CUS-03 | GET | `/customer/{customer_id}` | 客户详情、当前负责人和最近跟进 |
| CUS-04 | PATCH | `/customer/{customer_id}` | 修改白名单资料，不混改状态/负责人 |
| CUS-05 | PUT | `/customer/{customer_id}/status` | 按状态规则更新客户状态 |
| CUS-06 | POST | `/customer/{customer_id}/transfer` | 分派或移交负责人/部门 |
| CUS-07 | POST | `/customer/{customer_id}/archive` | 归档，保留销售状态和全部历史 |
| CUS-08 | POST | `/customer/{customer_id}/followups` | 追加跟进，实际跟进人取登录身份 |
| CUS-09 | GET | `/customer/{customer_id}/followups` | 按时间、跟进状态分页 |
| CUS-10 | PATCH | `/customer/{customer_id}/followups/{followup_id}` | 更正/调整/完成/取消跟进安排 |

#### 员工日报（基础 P0，整理与汇总 P1）

| 编号 | 方法 | 路径 | 功能重点 |
| --- | --- | --- | --- |
| DAY-01 | POST | `/daily-report/prepare` | 整理为临时预览（P1） |
| DAY-02 | POST | `/daily-report` | 本人首次正式提交日报 |
| DAY-03 | GET | `/daily-report` | 本人或授权部门查询 |
| DAY-04 | GET | `/daily-report/{daily_report_id}` | 正式内容、摘要、版本 |
| DAY-05 | PATCH | `/daily-report/{daily_report_id}` | 本人修订日报 |
| DAY-06 | POST | `/daily-report/{daily_report_id}/void` | 本人或纠错权限作废 |
| DAY-07 | POST | `/daily-report/summary` | 授权正式日报摘要（P1） |

#### 学生查询与成绩（P0）

| 编号 | 方法 | 路径 | 功能重点 |
| --- | --- | --- | --- |
| STU-01 | GET | `/students` | 返回授权学生列表 |
| STU-02 | GET | `/students/{student_id}` | 学生基础资料和授权职责关系 |
| SCO-01 | POST | `/scores` | 录入数值成绩 |
| SCO-02 | GET | `/scores` | 按条件筛选成绩 |
| SCO-03 | GET | `/scores/{score_id}` | 成绩详情与并发版本 |
| SCO-04 | PATCH | `/scores/{score_id}` | 更正成绩 |
| SCO-05 | POST | `/scores/{score_id}/void` | 作废误录成绩 |

#### 请假审批（P0）

| 编号 | 方法 | 路径 | 功能重点 |
| --- | --- | --- | --- |
| LEA-01 | GET | `/leave` | 查询 apply_type=leave 的申请 |
| LEA-02 | GET | `/leave/{apply_id}` | 申请详情与审批信息 |
| LEA-03 | POST | `/leave/{apply_id}/decision` | 当前审批人审批 |
| LEA-04 | POST | `/leave/{apply_id}/assign` | 有权分派者分派/转派 |
| LEA-05 | GET | `/leave/{apply_id}/records` | 审批时间线 |

#### 投诉与建议（P0）

| 编号 | 方法 | 路径 | 功能重点 |
| --- | --- | --- | --- |
| TIC-01 | GET | `/tickets` | 按条件筛选工单 |
| TIC-02 | GET | `/tickets/{ticket_id}` | 工单详情 |
| TIC-03 | POST | `/tickets/{ticket_id}/assign` | 分派或转派工单 |
| TIC-04 | POST | `/tickets/{ticket_id}/follow` | 追加回应或内部备注 |
| TIC-05 | POST | `/tickets/{ticket_id}/resolve` | 提交解决方案 |
| TIC-06 | GET | `/tickets/{ticket_id}/records` | 授权处理时间线 |

#### 心理预警人工处置（P0 跨模块）

| 编号 | 方法 | 路径 | 功能重点 |
| --- | --- | --- | --- |
| MEN-01 | GET | `/mental/warnings` | 查询授权预警 |
| MEN-02 | GET | `/mental/warnings/{warning_id}` | 预警详情 |
| MEN-03 | POST | `/mental/warnings/{warning_id}/assign` | 授权分派/转派 |
| MEN-04 | POST | `/mental/warnings/{warning_id}/ack` | 当前负责人接手 |
| MEN-05 | POST | `/mental/warnings/{warning_id}/follow` | 处理中追加跟进 |
| MEN-06 | POST | `/mental/warnings/{warning_id}/close` | 关闭预警 |
| MEN-07 | GET | `/mental/warnings/{warning_id}/records` | 授权处理时间线 |

#### 新人指南与制度问答（P1）

| 编号 | 方法 | 路径 | 功能重点 |
| --- | --- | --- | --- |
| KNO-01 | GET | `/knowledge` | 普通员工只见已发布有效授权资料 |
| KNO-02 | GET | `/knowledge/{knowledge_id}` | 知识详情 |
| KNO-03 | POST | `/knowledge/ask` | 知识问答（RAG） |

#### 待办与统一收件箱（P0）

| 编号 | 方法 | 路径 | 功能重点 |
| --- | --- | --- | --- |
| TODO-01 | GET | `/todos` | 本人或授权范围内待办 |
| TODO-02 | GET | `/todos/summary` | 待办分类统计 |
| NOT-01 | GET | `/notifications` | 合并两表站内收件通知 |
| NOT-02 | POST | `/notifications/{source}/{notification_id}/read` | 仅标记本人已读 |

#### 智能入口与语音（P1）

| 编号 | 方法 | 路径 | 功能重点 |
| --- | --- | --- | --- |
| AI-01 | POST | `/chat` | 对话意图与回答 |
| AI-02 | POST | `/nl2sql` | 仅返回授权结构化查询结果 |
| AI-03 | POST | `/command` | 解析注册动作，返回确认预览 |
| AI-04 | POST | `/command/confirm` | 校验后执行固定业务服务 |
| AI-05 | POST | `/audio/transcriptions` | 临时音频转写 |

#### 历史与执行回执（P0）

| 编号 | 方法 | 路径 | 功能重点 |
| --- | --- | --- | --- |
| LOG-01 | GET | `/operation-logs` | 按对象鉴权的变更历史 |
| LOG-02 | GET | `/operations/{operation_id}` | 本员工请求的执行状态 |

### 2.1.2 管理配套接口（第 6 节，复用公共能力）

| 编号 | 方法 | 路径 | 维护能力 |
| --- | --- | --- | --- |
| ADM-01 | POST | `/departments` | 创建部门 |
| ADM-02 | PATCH | `/departments/{department_id}` | 修改部门 |
| ADM-03 | POST | `/departments/{department_id}/status` | 部门启停 |
| ADM-04 | POST | `/employees` | 创建员工档案及初始角色 |
| ADM-05 | PATCH | `/employees/{employee_id}` | 修改员工资料 |
| ADM-06 | POST | `/employees/{employee_id}/status` | 员工启停/离职 |
| ADM-07 | PUT | `/employees/{employee_id}/roles` | 分配受控角色 |
| ADM-08 | POST | `/students` | 创建学生档案 |
| ADM-09 | PATCH | `/students/{student_id}` | 修改学生主数据 |
| ADM-10 | POST | `/students/{student_id}/archive` | 学生归档 |
| ADM-11 | GET | `/students/{student_id}/staff-bindings` | 查看职责关系 |
| ADM-12 | POST | `/students/{student_id}/staff-bindings` | 创建职责关系 |
| ADM-13 | PATCH | `/students/{student_id}/staff-bindings/{binding_id}` | 结束职责关系 |
| ADM-14 | POST | `/knowledge` | 创建知识草稿 |
| ADM-15 | PATCH | `/knowledge/{knowledge_id}` | 修改知识及范围 |
| ADM-16 | POST | `/knowledge/{knowledge_id}/publish` | 审核发布知识 |
| ADM-17 | POST | `/knowledge/{knowledge_id}/disable` | 停用知识 |
| ADM-18 | POST | `/knowledge/{knowledge_id}/reindex` | 重新索引 |
| ADM-19 | DELETE | `/knowledge/{knowledge_id}` | 删除未发布无引用草稿 |

## 2.2 角色清单（六个固定角色）

| 角色代码 | 角色名称 | 默认范围 |
| --- | --- | --- |
| `employee` | 普通员工 | 本人日报 |
| `consultant` | 客户顾问 | 本人负责客户、相关跟进及本人日报 |
| `manager` | 部门主管 | 本部门客户与已提交日报；子部门按固定配置明确 |
| `teacher` | 班主任/老师 | 有效关系分派的请假、学生及工单 |
| `academic` | 教务人员 | 授权学生/课程成绩 |
| `admin` | 管理员 | 员工、部门、知识配置；业务权限需相应角色 |

> **规则要点**
> - 不设置隐式角色继承；建议在职账号配置 `employee` 作为基础角色，其他职责通过 `role_codes` 数组兼任。
> - 允许一次业务操作，必须有一个角色规则完整满足“方法/动作 + 数据范围 + 当前对象条件”，不能拼接多个角色权限。
> - 未列入默认或明确条件授权的接口一律不开放。
> - 条件权限为后端固定配置，不新增第七个角色、不增加动态权限编辑器。

## 2.3 角色 × 接口 权限映射

### 2.3.1 公共入口（六角色均可使用，共 18 个）

| 接口编号 | 方法与路径 | 限制 |
| --- | --- | --- |
| ORG-01 | GET `/me` | 仅本人身份和受控功能列表 |
| ORG-02 | GET `/departments` | 可公开的组织树、职能和主管信息 |
| ORG-03 | GET `/employees` | 工作通讯录及必要工作字段 |
| ORG-04 | GET `/employees/{employee_id}` | 授权工作资料，非后台账号 |
| KNO-01 | GET `/knowledge` | 只查已发布、有效且本员工可见的资料 |
| KNO-02 | GET `/knowledge/{knowledge_id}` | 详情同样检查可见范围 |
| KNO-03 | POST `/knowledge/ask` | 仅检索该员工被授权的知识来源 |
| TODO-01 | GET `/todos` | 只返回本人或业务角色授权范围内的待办 |
| TODO-02 | GET `/todos/summary` | 统计范围与待办列表相同 |
| NOT-01 | GET `/notifications` | 仅本员工的站内收件通知 |
| NOT-02 | POST `/notifications/{source}/{notification_id}/read` | 仅标记本人通知 |
| AI-01 | POST `/chat` | 根据真实角色路由 |
| AI-02 | POST `/nl2sql` | 只查询该角色可读的受控视图和行 |
| AI-03 | POST `/command` | 只能预览该账号可执行的注册业务动作 |
| AI-04 | POST `/command/confirm` | 重新检查原业务动作权限 |
| AI-05 | POST `/audio/transcriptions` | 只转写临时音频 |
| LOG-01 | GET `/operation-logs` | 只返回本人允许查看的操作或授权对象历史 |
| LOG-02 | GET `/operations/{operation_id}` | 仅本人请求回执或授权对象的执行状态 |

### 2.3.2 普通员工 `employee`

除公共入口外，可调用以下 6 个本人日报接口：

| 接口编号 | 方法与路径 | 数据范围/限制 |
| --- | --- | --- |
| DAY-01 | POST `/daily-report/prepare` | 整理本人日报临时预览 |
| DAY-02 | POST `/daily-report` | 只能以登录员工为所属人提交 |
| DAY-03 | GET `/daily-report` | 仅本人；不得扩大到同事或部门 |
| DAY-04 | GET `/daily-report/{daily_report_id}` | 仅本人日报 |
| DAY-05 | PATCH `/daily-report/{daily_report_id}` | 本人修改或按规则恢复作废日报 |
| DAY-06 | POST `/daily-report/{daily_report_id}/void` | 仅本人且填写原因 |

> 默认不能调用客户、学生、成绩、请假、工单、心理处置、部门日报汇总和任何管理写接口。

### 2.3.3 客户顾问 `consultant`

除公共入口及 `employee` 的 6 个本人日报接口外，可调用：

| 接口编号 | 方法与路径 | 数据范围/限制 |
| --- | --- | --- |
| CUS-01 | POST `/customer` | 新增客户默认归本人及本人授权部门 |
| CUS-02 | GET `/customer` | `employee_id=当前员工` |
| CUS-03 | GET `/customer/{customer_id}` | 仅当前本人负责客户 |
| CUS-04 | PATCH `/customer/{customer_id}` | 仅本人客户基本资料白名单 |
| CUS-05 | PUT `/customer/{customer_id}/status` | 仅本人客户，遵守状态规则 |
| CUS-08 | POST `/customer/{customer_id}/followups` | 为本人当前负责客户追加跟进 |
| CUS-09 | GET `/customer/{customer_id}/followups` | 本人负责客户的完整授权跟进历史 |
| CUS-10 | PATCH | `/customer/{customer_id}/followups/{followup_id}` | 仅当前本人客户 |

> 默认不开放 CUS-06 移交、CUS-07 归档（由部门主管处理）。客户移交后前负责人不再读取整份客户资料或继续修改。

### 2.3.4 部门主管 `manager`

除公共入口外，可调用本部门客户管理和正式日报查阅接口：

| 接口编号 | 方法与路径 | 数据范围/限制 |
| --- | --- | --- |
| CUS-01 | POST `/customer` | 在本人管理部门创建客户，分派对象须为该部门有效顾问 |
| CUS-02 | GET `/customer` | 仅本人管理部门客户 |
| CUS-03 | GET `/customer/{customer_id}` | 本部门客户，不读其他部门 |
| CUS-04 | PATCH `/customer/{customer_id}` | 本部门客户基本资料 |
| CUS-05 | PUT `/customer/{customer_id}/status` | 本部门客户 |
| CUS-06 | POST `/customer/{customer_id}/transfer` | 本部门内首次分派/移交；跨部门默认拒绝 |
| CUS-07 | POST `/customer/{customer_id}/archive` | 本部门客户归档 |
| CUS-08 | POST `/customer/{customer_id}/followups` | 本部门客户追加本人实际执行的跟进 |
| CUS-09 | GET `/customer/{customer_id}/followups` | 本部门客户跟进历史 |
| CUS-10 | PATCH `/customer/{customer_id}/followups/{followup_id}` | 管理本部门客户跟进安排 |
| DAY-03 | GET `/daily-report` | 本部门 `submitted` 正式日报 |
| DAY-04 | GET `/daily-report/{daily_report_id}` | 同上，按提交部门快照校验 |
| DAY-07 | POST `/daily-report/summary` | 汇总本部门已提交日报 |

> 主管不代写/修改/作废下属日报；本人提交日报需兼任 `employee`。不自动取得学生、成绩、请假、工单、心理预警或管理配置权限。

### 2.3.5 班主任/老师 `teacher`

除公共入口外，默认可调用：

| 接口编号 | 方法与路径 | 数据范围/限制 |
| --- | --- | --- |
| STU-01 | GET `/students` | 有效班主任/服务关系或有效业务分派的学生 |
| STU-02 | GET `/students/{student_id}` | 同上，不默认返回课程成绩或心理信息 |
| LEA-01 | GET `/leave` | 当前分派本人、有效学生关系内的申请 |
| LEA-02 | GET `/leave/{apply_id}` | 同上 |
| LEA-03 | POST `/leave/{apply_id}/decision` | 当前 `reviewer_id=本人`、有效审批关系、`pending` |
| LEA-05 | GET `/leave/{apply_id}/records` | 仅有权申请的审批时间线 |
| TIC-01 | GET `/tickets` | 当前分派本人且有有效服务关系的工单 |
| TIC-02 | GET `/tickets/{ticket_id}` | 同上 |
| TIC-04 | POST `/tickets/{ticket_id}/follow` | 当前授权处理人工单 |
| TIC-05 | POST `/tickets/{ticket_id}/resolve` | 当前授权处理人、`processing`、仅进入待学生确认 |
| TIC-06 | GET `/tickets/{ticket_id}/records` | 仅授权工单时间线 |
| ADM-11 | GET `/students/{student_id}/staff-bindings` | 只查该授权学生与本人有关的职责 |

> 本人日报写入需兼任 `employee`。录入/更正/作废成绩需兼任 `academic`。LEA-04、TIC-03 及全部 MEN 接口按 2.3.8 附条件开放。

### 2.3.6 教务人员 `academic`

除公共入口外，可调用：

| 接口编号 | 方法与路径 | 数据范围/限制 |
| --- | --- | --- |
| STU-01 | GET `/students` | 有效成绩管理关系内的学生 |
| STU-02 | GET `/students/{student_id}` | 授权学生的必要基本档案 |
| SCO-01 | POST `/scores` | 授权学生 + `score_editor` 关系 + 课程范围 |
| SCO-02 | GET `/scores` | 授权学生及课程的成绩 |
| SCO-03 | GET `/scores/{score_id}` | 按记录中的学生/课程校验 |
| SCO-04 | PATCH `/scores/{score_id}` | 授权范围内更正得分/满分 |
| SCO-05 | POST `/scores/{score_id}/void` | 授权范围内作废 |
| ADM-11 | GET `/students/{student_id}/staff-bindings` | 只查看本人与该学生相关的成绩授权 |

> 本人日报需兼任 `employee`。不默认拥有请假审批、投诉处理、心理处置、学生档案维护或关系授权写权限。

### 2.3.7 管理员 `admin`

除公共入口外，可调用员工、部门和知识配置接口：

| 接口编号 | 方法与路径 | 数据范围/限制 |
| --- | --- | --- |
| ADM-01 | POST `/departments` | 平台授权维护的组织配置 |
| ADM-02 | PATCH `/departments/{department_id}` | 修改部门配置 |
| ADM-03 | POST `/departments/{department_id}/status` | 部门启停，先处理依赖 |
| ADM-04 | POST `/employees` | 员工主档、受控登录映射及初始角色 |
| ADM-05 | PATCH `/employees/{employee_id}` | 员工资料配置 |
| ADM-06 | POST `/employees/{employee_id}/status` | 员工启停/离职，检查未移交责任 |
| ADM-07 | PUT `/employees/{employee_id}/roles` | 六种角色分配，必须审计 |
| ADM-14 | POST `/knowledge` | 创建知识草稿 |
| ADM-15 | PATCH `/knowledge/{knowledge_id}` | 修改知识及访问范围 |
| ADM-16 | POST `/knowledge/{knowledge_id}/publish` | 审核发布 |
| ADM-17 | POST `/knowledge/{knowledge_id}/disable` | 停用知识 |
| ADM-18 | POST `/knowledge/{knowledge_id}/reindex` | 提交索引处理 |
| ADM-19 | DELETE `/knowledge/{knowledge_id}` | 仅未发布、无引用草稿 |

> 仅有 `admin` **不能**调用客户写接口、查看全公司日报、修改成绩、批准请假、处理学生投诉或读取心理预警。本人日报需兼任 `employee`。学生主档及关系维护 ADM-08~ADM-13 不在默认范围。

### 2.3.8 附条件接口（原角色表未明确授予）

> “条件”不由客户端传入，均在后端固定配置并留变更记录。

| 接口编号 | 方法与路径 | 建议角色及必要条件 | 未配置时 |
| --- | --- | --- | --- |
| LEA-04 | POST `/leave/{apply_id}/assign` | `teacher` 中被指定的分派负责人；限定学生/组织路由、待审批状态 | 默认拒绝 |
| TIC-03 | POST `/tickets/{ticket_id}/assign` | `teacher` 中被指定的服务分派负责人；限定处理部门、可分派人员与回避规则 | 默认拒绝 |
| MEN-01 | GET `/mental/warnings` | `teacher` + 心理专属处置功能 + 明确学生范围；通常 `follower_id=本人` | 默认拒绝，连计数和原因也不返回 |
| MEN-02 | GET `/mental/warnings/{warning_id}` | 同上，只读处置必需信息 | 默认拒绝 |
| MEN-03 | POST `/mental/warnings/{warning_id}/assign` | `teacher` 中被指定的心理分派负责人；未具内容权限时仅见最小路由字段 | 默认拒绝 |
| MEN-04 | POST `/mental/warnings/{warning_id}/ack` | 专属授权 teacher、当前负责人、有效关系、pending | 默认拒绝 |
| MEN-05 | POST `/mental/warnings/{warning_id}/follow` | 专属授权 teacher、当前负责人、processing | 默认拒绝 |
| MEN-06 | POST `/mental/warnings/{warning_id}/close` | 专属授权 teacher、当前负责人、processing、完整处置结果 | 默认拒绝 |
| MEN-07 | GET `/mental/warnings/{warning_id}/records` | 专属授权 teacher 且对该预警仍有处置/查阅权限 | 默认拒绝 |
| ADM-08 | POST `/students` | 优先可信教务同步服务；若人工维护，给指定 admin 增加明确学生主数据维护职责 | 默认拒绝人工写入 |
| ADM-09 | PATCH `/students/{student_id}` | 同上；只改主数据白名单 | 默认拒绝人工修改 |
| ADM-10 | POST `/students/{student_id}/archive` | 同上；另检查未结束业务及归档原因 | 默认拒绝 |
| ADM-11 | GET `/students/{student_id}/staff-bindings` | teacher/academic 默认仅查自己的授权关系；完整列表仅供被指定的学生授权维护 admin | 无维护职责时拒绝查看完整关系列表 |
| ADM-12 | POST `/students/{student_id}/staff-bindings` | 被指定的学生授权维护 admin；固定允许范围 | 默认拒绝 |
| ADM-13 | PATCH `/students/{student_id}/staff-bindings/{binding_id}` | 同上；结束旧关系、保留历史 | 默认拒绝 |

## 2.4 权限总览（按角色可用性）

| 接口 | employee | consultant | manager | teacher | academic | admin | 附条件 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ORG-01~04 | 公共 | 公共 | 公共 | 公共 | 公共 | 公共 | — |
| DAY-01~06 | ✅ | ✅ | 仅本人(兼任) | 仅本人(兼任) | 仅本人(兼任) | 仅本人(兼任) | — |
| DAY-03/04/07 | — | — | ✅本部门 | — | — | — | — |
| CUS-01~05/08/09/10 | — | ✅本人客户 | ✅本部门 | — | — | — | — |
| CUS-06/07 | — | — | ✅本部门 | — | — | — | — |
| STU-01/02 | — | — | — | ✅关系内 | ✅成绩关系内 | — | — |
| SCO-01~05 | — | — | — | 兼任academic | ✅ | — | — |
| LEA-01/02/03/05 | — | — | — | ✅当前分派 | — | — | — |
| LEA-04 | — | — | — | — | — | — | teacher分派负责人 |
| TIC-01/02/04/05/06 | — | — | — | ✅当前分派 | — | — | — |
| TIC-03 | — | — | — | — | — | — | teacher分派负责人 |
| MEN-01~07 | — | — | — | — | — | — | teacher心理专属授权 |
| KNO-01~03 | 公共 | 公共 | 公共 | 公共 | 公共 | 公共 | — |
| TODO-01/02, NOT-01/02 | 公共 | 公共 | 公共 | 公共 | 公共 | 公共 | — |
| AI-01~05 | 公共 | 公共 | 公共 | 公共 | 公共 | 公共 | — |
| LOG-01/02 | 公共 | 公共 | 公共 | 公共 | 公共 | 公共 | — |
| ADM-01~07 | — | — | — | — | — | ✅ | — |
| ADM-08~10 | — | — | — | — | — | — | 指定student维护admin |
| ADM-11 | — | — | — | ✅本人关系 | ✅本人关系 | — | 维护admin看全部 |
| ADM-12/13 | — | — | — | — | — | — | 指定student维护admin |
| ADM-14~19 | — | — | — | — | — | ✅ | — |
