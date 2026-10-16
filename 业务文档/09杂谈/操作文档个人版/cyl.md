# 智能报告模块设计方案

- 负责人：陈宇林（宇林）
- 整理日期：2026-10-16
- 依据：`业务文档/01需求拆解/智能报告.txt`、`业务文档/02需求文档/智能报告.md`、`业务文档/06开发文档/接口方案/智能报告/接口方案.md`、`业务文档/09杂谈/操作文档.md`、`scripts/sql/all.sql`、`C:\Users\Windows\Desktop\教育服务\客户需求表.xlsx`，以及当前 `app/`、`dify/`、`scripts/` 目录下的实际代码。

> 本文是智能报告模块的完整设计基线：覆盖角色、接口、权限、表（功能）、智能体接入、统一架构目录，以及各功能用到的 SQL 数据表与 ORM 模型。文中区分「已存在（当前代码已实现）」与「本方案新建 / 待办」，避免把方案当作已上线。

---

## 一、模块定位

智能报告模块是系统的「数据消费末端」：**不产生业务数据**，只做四件事——

1. 从企业 / 学生 / 客户研判等上游模块**只读**取数；
2. 按固定口径**计算指标**；
3. 调用 AI 对已算好的指标**写分析**（摘要 / 趋势 / 归因 / 建议）；
4. 保存报告正文与指标快照，供管理员 / 管理层查阅与配置。

操作顺序：`选报告类型和时间范围 → 提交生成（拿 pending + report_record_id）→ 轮询状态 → success 后看正文；failed 看失败原因`。

---

## 二、角色划分

| 角色 | 说明 | 能否访问本模块 |
| --- | --- | --- |
| 管理员 / 管理层（`admin` / `management`） | 报告的最终受众，看板前端使用者 | ✅ 全部 5 个接口 |
| 企业智能助手（可选互通） | 管理层通过企业助手对话调出报告 | 仅只读 `GET /report/list`、`GET /report/{id}`（默认不开放） |
| 业务模块（企业 / 学生 / 客服 / 客户研判） | 给报告模块供数据 | ❌ 只供数，不读报告 |
| 普通员工 / 顾问 / 主管 / 老师 / 教务 / 客户 / 学生 | 非管理层 | ❌ 无权 |

**结论：报告接口只对「管理员角色」开放。** 业务模块是供数据的，不是来读报告的。

---

## 三、接口设计（共 5 个 HTTP 接口）

统一前缀 `/api/v1`，统一响应信封 `{code, message, data}`，`code=0` 成功，请求头 `Authorization: Bearer <access_token>`。

| 编号 | 方法 | 路径 | 说明 |
| --- | --- | --- | --- |
| RPT-01 | POST | `/api/v1/report/generate` | 异步生成报告，立即返回 `report_record_id` + `status=pending` |
| RPT-02 | GET | `/api/v1/report/{report_record_id}` | 查单份报告（含正文与指标；心理周报匿名） |
| RPT-03 | GET | `/api/v1/report/list` | 分页列表，按 `report_code` / `status` 过滤，不含正文 |
| RPT-04 | GET | `/api/v1/report/configs` | 查 5 类报告配置 |
| RPT-05 | PUT | `/api/v1/report/configs/{report_code}` | 改名称 / cron / 启停，`row_version` 乐观锁 |

### 3.1 生成报告（RPT-01）

- 参数：`report_code`（五类之一，必填）、`start_time` / `end_time`（可选，不传按周期取最近完整周期）、`timezone`（默认 UTC）。
- 幂等：幂等键 = `report_code + 时间窗 + 版本`；完全相同重复请求返回已有记录，同键不同口径返回 409。
- 后台链路：`收单 → 建 pending 记录 → 后台任务取数算指标 → AI 写分析 → 写库 → success / failed`。

### 3.2 查询单份报告（RPT-02）

返回正文与指标快照。**脱敏规则：`mental_weekly` 对普通管理员只返回匿名聚合，不返回个人明细**；个人级明细仅授权页面 / 角色可见，不在本接口默认返回。

### 3.3 报告代码枚举

| report_code | 报告名称 | 周期 |
| --- | --- | --- |
| `customer_overview` | 全域客户经营分析报告 | week |
| `daily_report` | 员工日报汇总报告（日） | day |
| `weekly_report` | 员工日报汇总报告（周） | week |
| `mental_weekly` | 学生心理健康周报 | week |
| `complaint_weekly` | 投诉处理周报 | week |

---

## 四、权限设计

### 4.1 鉴权方式

复用小组统一鉴权：登录取得 Token → 每个受保护请求经公共 `get_current_account` / `require_permission` 校验身份 → 报告模块按「管理员角色」做业务授权。**报告路由当前没有鉴权依赖，是首要待办**。

### 4.2 权限点（建议新增，写入 `app/access_control.yaml`）

| 权限点 | 用途 | 对应接口 |
| --- | --- | --- |
| `report.generate` | 生成报告 | RPT-01 |
| `report.read` | 查看报告（列表 + 单份匿名内容） | RPT-02、RPT-03 |
| `report.config.read` | 查看报告配置 | RPT-04 |
| `report.config.write` | 修改报告配置 | RPT-05 |
| `report.mental_detail.read` | 心理周报个人级明细 | 默认不授予，仅授权页面 / 角色 |

### 4.3 角色 × 接口权限矩阵

| 接口 | admin / management | 企业助手（可选只读） | 其他角色 |
| --- | --- | --- | --- |
| RPT-01 生成 | ✅ | ❌ | ❌ |
| RPT-02 查单份 | ✅（心理周报脱敏） | ✅（可选互通） | ❌ |
| RPT-03 列表 | ✅ | ✅（可选互通） | ❌ |
| RPT-04 查配置 | ✅ | ❌ | ❌ |
| RPT-05 改配置 | ✅（乐观锁） | ❌ | ❌ |

### 4.4 需要收紧的两处现状

1. `app/access_control.yaml` 现有 `employee` 角色包含 `report.read`，与本方案「仅管理员可读」冲突；应由公共鉴权负责人统一调整为仅 `admin` 拥有 `report.*` 权限。
2. 页面可见性不等于接口授权：前端看板只控制显示，后端仍须逐个接口做角色校验。

### 4.5 心理周报脱敏（重点）

- 心理数据是敏感数据：`mental_weekly` 正文与指标**默认只输出匿名聚合**（总评估数、风险等级分布、预警数、趋势），不输出 `student_id`、个人情绪分值、个人预警原因等明细。
- 个人级明细另设 `report.mental_detail.read` 权限，仅授权角色可见；服务代码里的脱敏 `TODO` 需落实为固定过滤逻辑，不能靠提示词兜底。

---

## 五、表（功能）设计

### 5.1 报告模块专属三张表（已落地，统一建表脚本中）

三张表位于 `scripts/sql/all.sql`（与 `scripts/sql/bk/智能报告/report_module_ddl.sql` 完全一致）。时间统一 UTC、DATETIME(3)；代码 / 状态 / 幂等键列使用 `utf8mb4_bin` 排序规则。

#### 5.1.1 `report_config`（报告配置表）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `report_config_id` | BIGINT | 主键，自增 |
| `report_code` | VARCHAR(64) utf8mb4_bin | 报告代码，唯一，五类枚举（CHECK） |
| `report_name` | VARCHAR(128) | 报告名称 |
| `report_period` | VARCHAR(16) utf8mb4_bin | 报告周期，默认 `week`：day / week / month |
| `cron_expr` | VARCHAR(64) | 定时表达式（cron，按东八区配置），可空 |
| `enabled` | BOOLEAN | 是否启用，默认 1：1 启用、0 停用 |
| `created_at` | DATETIME(3) | 记录创建时间，UTC |
| `updated_at` | DATETIME(3) | 最近更新时间，UTC |
| `row_version` | INT | 并发版本号，默认 1，每次业务修改递增 |

约束：`UNIQUE(report_code)`；CHECK `report_code IN ('customer_overview','daily_report','weekly_report','mental_weekly','complaint_weekly')`、`report_period IN ('day','week','month')`、`enabled IN (0,1)`、`row_version >= 1`。

#### 5.1.2 `report_record`（报告生成记录表）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `report_record_id` | BIGINT | 主键，自增 |
| `report_config_id` | BIGINT | 报告配置 ID，FK → `report_config.report_config_id` |
| `report_code` | VARCHAR(64) utf8mb4_bin | 报告代码（冗余，便于按类型检索） |
| `idempotency_key` | VARCHAR(128) utf8mb4_bin | 幂等键：report_code + 时间窗 + 版本，唯一 |
| `start_time` | DATETIME(3) | 统计起始时间，UTC |
| `end_time` | DATETIME(3) | 统计截止时间，UTC，必须晚于起始 |
| `timezone` | VARCHAR(32) | 统计口径时区，默认 `UTC` |
| `data_snapshot_at` | DATETIME(3) | 数据快照时间，用于指标可复算，可空 |
| `report_version` | VARCHAR(32) utf8mb4_bin | 报告生成版本，默认 `v1`，参与幂等键 |
| `source_record_count` | INT | 来源记录数，默认 0，用于追溯与识别数据不足 |
| `report_content` | LONGTEXT | 报告正文（AI 生成的结构化文本），可空 |
| `metric_json` | JSON | 可复算指标快照，可空 |
| `status` | VARCHAR(32) utf8mb4_bin | 状态，默认 `pending`：pending / running / success / failed |
| `fail_reason` | TEXT | 失败原因，可空 |
| `generated_at` | DATETIME(3) | 生成完成时间，UTC，可空 |
| `created_at` | DATETIME(3) | 记录创建时间，UTC |
| `updated_at` | DATETIME(3) | 最近更新时间，UTC |
| `row_version` | INT | 并发版本号，默认 1 |

约束：`UNIQUE(idempotency_key)`；CHECK `end_time > start_time`、`status IN ('pending','running','success','failed')`、`source_record_count >= 0`、`row_version >= 1`；索引 `idx_report_record_config`、`idx_report_record_code_time`、`idx_report_record_status`。

#### 5.1.3 `report_metric`（报告指标明细表）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `report_metric_id` | BIGINT | 主键，自增 |
| `report_record_id` | BIGINT | 所属报告记录 ID，FK → `report_record.report_record_id` |
| `metric_code` | VARCHAR(64) utf8mb4_bin | 指标代码 |
| `metric_name` | VARCHAR(128) | 指标名称 |
| `metric_value` | DECIMAL(20,4) | 指标数值（数值型指标），可空 |
| `metric_text` | TEXT | 指标文本值（非数值型指标），可空 |
| `metric_unit` | VARCHAR(32) | 单位，可空 |
| `calc_rule` | TEXT | 计算口径 / 规则说明，用于指标复算，可空 |
| `period_type` | VARCHAR(16) utf8mb4_bin | 周期类型：day / week / month，可空 |
| `created_at` | DATETIME(3) | 记录创建时间，UTC |

约束：CHECK `metric_value IS NOT NULL OR metric_text IS NOT NULL`；`period_type` 为 NULL 或三枚举之一；索引 `idx_report_metric_record`、`idx_report_metric_code`。

五类报告配置种子数据（`report_code` / 周期 / cron）：

```text
customer_overview   week   0 0 9 * * 5
daily_report        day    0 30 18 * * *
weekly_report       week   0 0 9 * * 5
mental_weekly       week   0 0 9 * * 5
complaint_weekly    week   0 0 9 * * 5
```

### 5.2 五类报告的源表（只读，不新建、不回写）

| report_code | 源表（只读） | 落地状态 |
| --- | --- | --- |
| `customer_overview` | `customer_profile`、`customer_followup`、`customer_judgement`（研判表，**未落地**） | 客户 / 跟进指标已有，研判关联未接入 |
| `daily_report` | `employee_daily_report` | 已有提交数 / 作废数 / 提交人数 |
| `weekly_report` | `employee_daily_report` | 与日报共用取数，时间窗按周 |
| `mental_weekly` | `mental_health_profile`、`mental_warning` | **取数未接入**，需补 |
| `complaint_weekly` | `service_ticket` | 已有总量与状态计数，未按 `ticket_type` 区分投诉 / 建议 |

---

## 六、智能体（Agent）接入设计

### 6.1 哪个接口要接入 Agent

**只有 RPT-01（生成报告）需要接入智能体。** 其余四个接口（查单份 / 列表 / 查配置 / 改配置）是纯 CRUD / 查询，不接 AI。

| 接口 | 是否接 Agent | 说明 |
| --- | --- | --- |
| RPT-01 生成 | ✅ | 后台任务取数后，调「智能报告生成」Workflow 写分析正文 |
| RPT-02 查单份 | ❌ | 纯读取 `report_record` / `report_metric` |
| RPT-03 列表 | ❌ | 纯读取元数据 |
| RPT-04 查配置 | ❌ | 纯读取 `report_config` |
| RPT-05 改配置 | ❌ | 固定规则 + 乐观锁 |

### 6.2 对应的智能体及其功能

智能体 = **「智能报告生成」Dify Workflow**（`dify/report/report.yml`，模型 `deepseek-v4-pro`，节点：`用户输入 → LLM → 输出`）。

| 项目 | 内容 |
| --- | --- |
| 智能体名称 | 智能报告生成 |
| 输入 | `report_code`（报告类型）、`metrics`（已算好的指标 JSON 文本） |
| 功能 | 基于传入指标写结构化中文报告正文：**摘要 / 趋势 / 归因 / 建议**，用 Markdown 小标题组织 |
| 输出 | `data.outputs.report_text` |
| 关键约束 | **严禁编造 / 估算输入指标里不存在的数字**，正文必须只引用传入数字 |
| 调用方 | `app/clients/report_dify.py` → `ReportDifyClient.generate_report()` |

### 6.3 固定代码 vs 模型分工（与企业管理模块同款原则）

- **固定后端代码负责**：鉴权、取数（固定参数化 SQL）、算指标、幂等、状态流转、写库、失败兜底、`<think>` 思考过程剥离。
- **模型只负责**：把已算好的数字写成可读的分析文字，**不做任何取数、不编数字、不写库**。

### 6.4 取数方式与 NL2SQL 依赖（未来）

- 当前取数用**固定 SQL**（`_fetch_metrics`），保证指标稳定、可复现。
- 接口方案提出：组长提供「统一 NL2SQL 查询服务（只读 + 白名单 + 行权限）」后，可把固定 SQL 换成 NL2SQL 调用。**这是待办，非当前实现**；切换后仍需保留固定口径校验，不能让模型自由生成 SQL 后直接执行。

### 6.5 与其它智能体的边界（不要重复造）

- 员工日报「内容级摘要」（核心进展 / 关键产出 / 潜在风险）属于企业模块 `DAY-07 daily_summary` 的职责；报告模块的日报 / 周报当前只做**数量级固定指标**。若需求要求内容级汇总，应由报告模块**复用企业模块的日报摘要结果（`employee_daily_report.ai_summary`）或调用其 agent**，不在报告模块另建一个日报摘要智能体。
- 心理周报的「风险识别」由学生模块 `S12 / MEN-*` 完成并写入 `mental_health_profile` / `mental_warning`；报告模块**只读**这些结果做聚合，不自行再做情绪识别。

---

## 七、统一架构目录（要建哪些文件、放哪）

以下沿用全项目分层目录（`app/` 技术层共用，不另建五套专属代码文件夹）。标注「已存在」的是当前代码已就位的文件，「新建」是本方案提出要补的文件。

```text
StuProject/
  app/
    api/report.py                     已存在：5 个 HTTP 路由（待补管理员鉴权依赖）
    services/report_service.py        已存在：配置读写 + 异步生成链路
    services/report_metrics.py        新建：五类报告取数与固定指标计算（从 report_service 拆出）
    services/report_anonymizer.py     新建：心理周报匿名脱敏
    models/report.py                  已存在：ReportConfig / ReportRecord / ReportMetric
    schemas/report.py                 已存在：请求 / 响应 Pydantic 契约
    clients/report_dify.py            已存在：Dify 报告生成 Workflow 适配器
    core/report_auth.py               新建：报告模块管理员鉴权依赖（复用 core/authorization）
    tasks/report_tasks.py             新建：定时生成（把 report_config.cron_expr 落地为真实调度）
  dify/report/
    report.yml                        已存在：智能报告生成 Workflow DSL
    README.md                         已存在：Workflow 导入 / 发布 / 调用说明
  scripts/
    init_report_tables.py             已存在：三张表初始化（--dry-run / --check / --apply）
    run_report_tasks.py               新建：独立调度进程（可选，参考学生模块 run_student_tasks.py）
  scripts/sql/bk/智能报告/
    report_module_ddl.sql             已存在：模块 DDL（与 all.sql 完全一致）
  业务文档/06开发文档/接口方案/智能报告/
    接口方案.md                        已存在：接口与角色权限抽取
  业务文档/09杂谈/操作文档个人版/陈宇林/
    智能报告设计方案.md                新建：本文档
```

### 关键新建文件职责

| 文件 | 职责 |
| --- | --- |
| `app/services/report_metrics.py` | 集中管理五类报告的固定取数 SQL 与指标字典；补 `mental_weekly` 取数；`complaint_weekly` 按 `ticket_type='complaint'` 对齐口径；指标 key 从中文占位改为稳定英文 `metric_code` |
| `app/services/report_anonymizer.py` | 心理周报匿名聚合过滤，个人明细仅在授权下输出 |
| `app/core/report_auth.py` | 基于公共 `require_permission` 组装报告模块管理员依赖，供 `app/api/report.py` 挂到 5 个路由 |
| `app/tasks/report_tasks.py` + `scripts/run_report_tasks.py` | 读取 `report_config.cron_expr` 触发定时生成，补上当前缺失的定时执行能力 |

---

## 八、各功能用到的 SQL 数据表与 ORM 模型

### 8.1 报告模块自有 ORM 模型（`app/models/report.py`，三张）

| ORM 模型 | 对应 SQL 表 | 用途 |
| --- | --- | --- |
| `ReportConfig` | `report_config` | 配置读写（RPT-04 / RPT-05） |
| `ReportRecord` | `report_record` | 生成任务与报告正文（RPT-01 / RPT-02 / RPT-03） |
| `ReportMetric` | `report_metric` | 指标明细，指标可复算 |

### 8.2 源表只读（固定 SQL，报告模块不持有这些表的 ORM 模型）

> 报告模块对上游表**只用固定参数化 SQL 读，不建 ORM 模型、不写回**。上游表的 ORM 模型由各自业务模块维护（当前 `app/models/` 下仅 `agent.py`、`student_leave.py`、`report.py`、`user_account.py`；`employee` / `customer_profile` / `service_ticket` 等企业表尚未建 ORM，报告模块只按 `scripts/sql/all.sql` 的列名读）。

### 8.3 逐功能映射表

| report_code（功能） | 读哪些 SQL 表 | 关键字段（用于指标） | 产出指标 | ORM 模型 |
| --- | --- | --- | --- | --- |
| `customer_overview` 全域客户经营分析 | `customer_profile`、`customer_followup` | `customer_profile.status`（new/contacting/qualified/signed/lost）、`is_archived`、`created_at`、`lost_reason`；`customer_followup.followup_at`、`followup_status` | 客户总数、窗口内新增、各状态计数、窗口内跟进数、流失数及归因 | 自有 `ReportConfig` / `ReportRecord` / `ReportMetric` |
| `daily_report` 员工日报汇总（日） | `employee_daily_report` | `status`（submitted/void）、`employee_id`、`report_date` | 提交数、作废数、提交人数 | 同上 |
| `weekly_report` 员工日报汇总（周） | `employee_daily_report` | 同上，时间窗按周 | 同上 | 同上 |
| `mental_weekly` 学生心理健康周报 | `mental_health_profile`、`mental_warning` | `mental_health_profile.risk_level`、`emotion_score`、`observed_at`；`mental_warning.risk_level`、`follower_status`、`created_at` | 评估次数、风险等级分布、预警数、预警处置状态、情绪趋势（匿名聚合） | 同上 |
| `complaint_weekly` 投诉处理周报 | `service_ticket` | `ticket_type`（complaint/suggestion）、`status`、`category_code`、`first_response_at`、`created_at`、`resolved_at`、`closed_at`、`satisfaction_score` | 投诉总量、各状态计数、分类计数、处理时效、满意度、长期未决预警 | 同上 |

### 8.4 依赖的共享 / 待落地表

| 表 / 事项 | 说明 |
| --- | --- |
| `customer_judgement` | 客户研判结果表，**尚未落地**；全域客户经营分析的「成交转化 / 流失归因」研判维度依赖它，排最后做 |
| `customer_profile.deal_amount` | 成交金额，**尚未落地**；如需精确营收指标，由企业模块在 `customer_profile` 补充 |
| `operation_log` | 报告模块的配置修改、生成动作如需审计，可复用（当前方案未强制） |

---

## 九、当前状态与待办清单

**已实现：**
- 5 个接口路由（`app/api/report.py`），`main.py` 已挂载报告路由。
- 三张专属表 ORM + DDL + 初始化脚本 + 5 条配置种子数据。
- 日报 / 周报、投诉周报、客户档案 / 跟进的部分固定指标取数。
- 「智能报告生成」Dify Workflow DSL 与调用客户端。

**待办（本方案明确）：**

| 序号 | 待办 | 优先级 |
| --- | --- | --- |
| 1 | 给 5 个报告路由补管理员鉴权依赖（`app/core/report_auth.py`） | 高 |
| 2 | 收紧 `access_control.yaml`：`report.*` 仅授予 admin，移除 employee 的 `report.read` | 高 |
| 3 | 心理周报脱敏落地（`report_anonymizer.py`），替换服务里的 TODO | 高 |
| 4 | 补 `mental_weekly` 取数（`mental_health_profile` / `mental_warning` 聚合） | 中 |
| 5 | `complaint_weekly` 按 `ticket_type='complaint'` 对齐统计口径 | 中 |
| 6 | 指标 key 改为稳定英文 `metric_code`，替换中文占位 | 中 |
| 7 | 定时生成落地（`app/tasks/report_tasks.py` + 调度进程），当前仅存 cron 配置、无真实调度 | 中 |
| 8 | 接入统一 NL2SQL（等组长服务就绪后替换固定 SQL，保留白名单与口径校验） | 低 |
| 9 | `customer_judgement` 落地后接入经营分析研判维度 | 低 |

> 本文基于现有资料与代码整理，未执行建表、写库或外部服务调用；「已实现」不代表已部署或通过联调。
