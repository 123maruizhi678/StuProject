# 全模块合并文档（allm.md）：公共基础能力 + 客服 Agent + 客户信息研判

主模块（主体）：公共登录与权限入口（公共基础能力，负责人 马睿智）  
已合并模块一：客服 Agent（对外开放模块，负责人 何至朗）  
本次合并模块二：客户信息研判（客户信息接入、解析结构化、画像研判、结果输出）  
整理日期：2026-10-16  
系统目录：`D:\AI\StuProject`

本文件以「马睿智操作文档：公共基础能力与客服 Agent 联动版」（下称主文档）为主体，把「客户信息研判模块」的目录结构、数据库表、接口与功能合并进来，形成统一的全模块操作说明。目录名与文件名沿用源文档原文，未读取实际磁盘目录；「当前可见 / 源文档列出 / 规划中 / 待交付」等状态均按源文档保留，不代表已完成代码合并或功能验收。

## 阅读口径

- 第一、二章是本次合并的总体范围、目录结构与命名冲突处理。
- 第三章是数据库表结构及关联关系，含新增客户研判五表与字段/表关联冲突的解决。
- 第四章是功能联动设计与调用流程，含权限联动、客户研判主线、客服与研判联动、研判与客户主档联动。
- 第五章是分阶段合并步骤、数据迁移、向后兼容与注意事项。
- 第六章是合并验收要点。

本次交付为文档，不修改代码、不建表、不部署、不迁移数据；不含实现代码示例。三方功能按源文档职责划分：公共模块负责认证、鉴权、日志、统一返回、Dify HTTP、数据库会话、配置；客服模块维护六个匿名接口与六表；客户研判模块维护八个受保护接口与五表。公共能力由三方复用，同一公共文件只保留一份实现。

---

## 一、合并总览

### 1.1 合并对象与范围

| 模块 | 来源 | 接口 | 数据库表 | 鉴权方式 |
| --- | --- | --- | --- | --- |
| 公共基础能力 | 主文档（主体） | `POST /api/v1/auth/login`、`GET /api/v1/auth/public-access`、`GET /api/v1/auth/me/access` | `user_account`、`org_department`、`employee`、`customer_profile`、`student_profile`（及外键依赖） | JWT + `Depends(require_permission(...))` |
| 客服 Agent | 主文档（已合并） | `agent/chat`、`agent/events`、`agent/events/{id}`、`agent/events/signup`、`agent/courses`、`agent/faq` | `course_project`、`lecture_event`、`event_signup`、`faq`、`chat_session`、`chat_message` | 匿名开放，无需 JWT |
| 客户信息研判 | sgt.md（本次合并） | `customer/sources`、`customer/sources/{id}/parse`、`customer/judge`、`customer/judge/batch`、`customer/results/{id}`、`customer/results`、`customer/rules`（GET/PUT） | `customer_source`、`customer_info`、`research_rule`、`product`、`research_result` | JWT + `require_permission(customer.*)` |

客户研判的八个接口为基础前缀 `/api/v1` 下的受保护接口，需登录并具备对应 `customer.*` 权限；不与客服六个匿名接口混用授权规则。客户研判为全新模块（sgt.md 标注「规划中」），本次合并以「新增表 + 新增接口 + 接入公共能力」为主，不改造存量客服与公共契约。

### 1.2 合并原则

1. **保留原有核心功能**：公共三个接口、客服六个接口的路径、请求/响应字段、匿名开放规则不变；客服六表与公共五表字段、索引、外键、CHECK 约束不变。
2. **向后兼容**：不新增 `user_account.identity_type` 取值、不修改既有 CHECK 约束、不改变已签发 JWT 的语义；客户研判权限通过既有身份 + `employee.role_codes` 细分接入。
3. **统一目录层级**：公共文件（main.py、config.py、database.py、core/*、schemas/auth.py、scripts/sql/all.sql 等）只保留一份，三方复用；客服与客户研判业务文件按 `api/`、`services/`、`models/`、`schemas/`、`clients/` 并列存放，不复制平行代码。
4. **冲突先比较再合并**：同名文件由主责负责人审核业务语义后合并，不无条件覆盖；不同目录中的同名文件按完整相对路径区分。
5. **数据迁移条件化**：客户研判五表为新增表，优先走增量建表；只有目标库已存在同名表或需要跨副本归并数据时才执行迁移，不执行含 DROP 的全量重建。

---

## 二、合并后的目录结构

### 2.1 统一目录树

目录名与文件名沿用源文档原文（客服资产、客户研判文件均按 sgt.md/主文档列出的名字），未读取实际目录。括号标注主责模块：〔公共〕〔客服〕〔客户研判〕〔待交付/可选〕。

```text
D:/AI/StuProject/
├── .env                               项目配置：数据库、日志、JWT 及各业务 Dify 凭据〔公共+客服+客户研判合并，真实值不入文档〕
├── environment.yml                    项目运行环境及依赖声明〔公共，合并三方依赖〕
├── dify/                              Dify 应用与知识库资产
│   ├── 客服Agent-Chatflow.yml         客服 Workflow DSL〔客服，待交付〕
│   ├── customer-extract.yml           客户研判字段抽取 Workflow DSL〔客户研判，可选/待交付〕
│   ├── README.md                      Dify 资产导入与维护说明〔待交付〕
│   └── knowledge/
│       ├── README.md                  知识库维护流程〔待交付〕
│       ├── 公司信息.md                 公司信息知识库〔客服〕
│       ├── 公司业务.md                 公司业务知识库〔客服〕
│       ├── 留学政策.md                 留学政策知识库〔客服〕
│       ├── FAQ.md                     FAQ 知识库〔客服〕
│       ├── 客户画像研判规则.md          《用户画像研判规则》源文件〔客户研判，依据甲方文件〕
│       └── dataset_ids.json           知识库 dataset_id/document_id 映射〔客服〕
├── app/
│   ├── main.py                        FastAPI 入口：挂载 auth、agent、customer 路由〔公共，合并三方挂载〕
│   ├── config.py                      统一配置：公共 + 客服 + 客户研判配置项〔公共〕
│   ├── database.py                    数据库连接池、ORM 基类、请求级会话及释放〔公共〕
│   ├── access_control.yaml            身份权限映射：公共 + 客户研判 customer.* 权限〔公共〕
│   ├── api/
│   │   ├── auth.py                    登录、公开清单、当前用户权限清单〔公共〕
│   │   ├── agent.py                   客服六个 HTTP 接口〔客服〕
│   │   └── customer.py                客户研判八个 HTTP 接口〔客户研判〕
│   ├── core/
│   │   ├── auth.py                    JWT 身份认证依赖〔公共〕
│   │   ├── authorization.py           逐接口权限鉴权组件〔公共〕
│   │   ├── logger.py                  日志初始化与获取〔公共〕
│   │   ├── response.py                统一返回模型、业务异常及全局异常处理〔公共〕
│   │   └── dify.py                    本地 Dify 同步/异步 JSON HTTP 请求封装〔公共〕
│   ├── services/
│   │   ├── auth_service.py            账号密码校验、密码哈希、JWT 签发/解析〔公共〕
│   │   ├── agent_service.py           客服对话、报名、课程、FAQ 业务〔客服〕
│   │   ├── dify_client.py             客服 mock / real 客户端及切换〔客服〕
│   │   ├── customer_service.py        客户研判接入、解析调度、结果组装〔客户研判〕
│   │   ├── parser.py                  多格式解析：文本、PDF、Excel 分派与归一化〔客户研判〕
│   │   ├── extractor.py               关键字段提取逻辑〔客户研判〕
│   │   └── judge_service.py           画像研判规则引擎：加载规则、逐条比对〔客户研判〕
│   ├── models/
│   │   ├── user_account.py            公共账号 ORM〔公共〕
│   │   ├── agent.py                   客服六表 ORM〔客服〕
│   │   ├── customer_source.py         客户信息来源表 ORM〔客户研判〕
│   │   ├── customer_info.py           客户关键字段表 ORM〔客户研判〕
│   │   ├── research_rule.py           研判规则表 ORM〔客户研判〕
│   │   ├── product.py                 甲方产品表 ORM〔客户研判〕
│   │   └── research_result.py         研判结果表 ORM〔客户研判〕
│   ├── schemas/
│   │   ├── auth.py                    登录请求字段及参数约束〔公共〕
│   │   ├── agent.py                   客服请求/响应字段〔客服〕
│   │   └── customer.py                客户研判请求/响应字段〔客户研判〕
│   ├── clients/                       各业务 Dify 适配器，复用公共 HTTP 工具
│   │   ├── nl2sql_dify.py             NL2SQL 场景适配〔公共，场景负责人维护〕
│   │   ├── report_dify.py             报告场景适配〔公共，场景负责人维护〕
│   │   └── extract_dify.py            客户研判字段抽取适配〔客户研判〕
│   └── logs/                          默认运行日志输出目录〔公共〕
└── scripts/
    ├── sql/
    │   ├── all.sql                    统一建表脚本：公共 + 客服 + 客户研判〔公共/数据库负责人〕
    │   └── agent_seed.sql             客服种子数据〔客服，待交付〕
    ├── reupload_dify_kb.py            知识库重传脚本〔客服，待交付〕
    ├── test_dify_kb.py                知识库检索验证〔客服，待交付〕
    └── test_workflow_run.py           客服工作流联调〔客服，待交付〕
```

各 Python 包内的 `__init__.py` 省略。`clients/` 中三个适配器只说明公共 HTTP 工具的调用位置，模型配置、Prompt、知识库与输出解析归各场景负责人。客户研判的 `extract_dify.py` 仅在启用大模型辅助解析时使用；规则判定不依赖它。

### 2.2 命名与路径冲突处理

客户研判新增文件与客服文件无同名冲突（`agent.*` vs `customer.*`、`customer_source` 等），冲突集中在三方共用的公共文件。处理规则如下：

| 相对路径 | 冲突类型 | 主责与合并方式 | 必须保留/核对的内容 |
| --- | --- | --- | --- |
| `app/main.py` | 三方共用 | 公共负责人汇总路由挂载与生命周期 | auth、agent、customer 三组路由按交付状态挂载；其他模块路由保留；异常注册不重复 |
| `app/config.py` | 三方共用 | 公共负责人合并配置字段 | JWT、权限、DB、日志、客服 Dify 配置 + 客户研判 Dify/规则配置；同名不同含义不取并集 |
| `app/database.py` | 三方共用 | 逐项比较，保留唯一数据库入口 | 同一 Base/元数据、连接池、会话、UTC 约定及释放；不自动建表 |
| `app/access_control.yaml` | 公共 + 客户研判 | 公共负责人审核权限映射 | 保留客服匿名开放不受影响；新增 `customer.*` 权限及员工角色细分；不新增 identity_type |
| `app/api/auth.py` | 三方共用 | 公共负责人确认契约 | 三个公共接口契约、JWT 返回字段及既有调用方兼容 |
| `app/core/*`（auth/authorization/logger/response/dify） | 三方共用 | 公共负责人维护唯一实现 | 签名/有效期、权限拒绝路径、日志幂等、错误出口、同步/异步 HTTP 契约 |
| `app/schemas/auth.py` | 三方共用 | 公共负责人审核 | 登录字段、长度及既有错误约定 |
| `scripts/sql/all.sql` | 三方共用 | 数据库负责人逐表审核 | 公共五表 + 客服六表 + 客户研判五表字段/索引/约束；运行库升级用增量迁移，不 DROP 重建 |
| `.env` | 三方共用 | 部署环境逐项映射，原配置受控备份 | 不拼接密钥、不披露真实值；同名冲突按目标环境选择 |
| `environment.yml` | 三方共用 | 依赖负责人核对兼容 | 认证/HTTP/数据库驱动；客户研判若引入 PDF/Excel 解析依赖需一并声明，不简单取并集 |

客服专属 `api/agent.py`、`services/agent_service.py`、`services/dify_client.py`、`models/agent.py`、`schemas/agent.py` 由客服负责人维护；客户研判专属 `api/customer.py`、`services/customer_service.py`、`services/parser.py`、`services/extractor.py`、`services/judge_service.py`、`models/customer_*.py`、`models/product.py`、`models/research_*.py`、`schemas/customer.py`、`clients/extract_dify.py` 由客户研判负责人维护。两者与公共组件一起回归。

---

## 三、数据库表结构及关联关系

### 3.1 表总览

合并后共三类、16 张相关表：

| 类别 | 表名 | 归属 | 说明 |
| --- | --- | --- | --- |
| 公共账号及依赖 | `user_account`、`org_department`、`employee`、`customer_profile`、`student_profile` | 公共 | 主文档第九章已列全字段、索引、外键、CHECK，本次不改动 |
| 客服业务 | `course_project`、`lecture_event`、`event_signup`、`faq`、`chat_session`、`chat_message` | 客服 | 主文档第一章已列完整 47 字段，本次不改动 |
| 客户研判 | `customer_source`、`customer_info`、`research_rule`、`product`、`research_result` | 客户研判 | 新增，字段见 3.2 |

客户研判五表为新增，与既有 11 表不存在同名表冲突。存量 `course_project`、`customer_profile` 等表保持原结构，不因本次合并增删字段。

### 3.2 新增客户研判五表完整字段（依据需求整理的设计口径）

以下字段依据 sgt.md 及《客户研判需求文档》整理，为设计口径；具体类型、默认值、索引、外键与 CHECK 待甲方《用户画像研判规则》和团队 DDL 约定确定后再冻结。时间字段沿用既有表 `DATETIME(3) UTC` 与 `row_version` 并发约定。

##### 3.2.1 甲方产品表 `product`

存甲方对外产品线（本次需求为两个产品），是画像研判的判定对象与规则归属。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| id | BIGINT | 否 | 自增 | 主键 |
| product_code | VARCHAR(32) | 否 | — | 产品唯一编码，唯一键 |
| product_name | VARCHAR(100) | 否 | — | 产品名称 |
| description | TEXT | 是 | NULL | 产品说明 |
| target_profile_summary | TEXT | 是 | NULL | 目标客户画像摘要（规则判定口径的说明） |
| status | VARCHAR(32) | 否 | 'active' | 状态：active 启用 / disabled 停用 |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间（UTC） |
| updated_at | DATETIME(3) | 否 | 当前时间，更新时自动刷新 | 更新时间（UTC） |
| row_version | INT | 否 | 1 | 并发版本号 |

- 唯一键 `uq_product_code(product_code)`；索引 `idx_product_status(status)`。

##### 3.2.2 客户信息来源表 `customer_source`

一次接入（一份文本、一份 PDF、一个 Excel 文件）对应一条来源记录；一个 Excel 文件可解析出多条客户。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| id | BIGINT | 否 | 自增 | 主键 |
| source_type | VARCHAR(16) | 否 | — | 来源类型：text / pdf / excel |
| raw_content | LONGTEXT | 是 | NULL | 归一化后的原始文本；文本类直接存，文件类存解析结果 |
| file_name | VARCHAR(255) | 是 | NULL | 原始文件名 |
| file_path | VARCHAR(255) | 是 | NULL | 文件存放路径（文件类来源） |
| status | VARCHAR(32) | 否 | 'pending' | 状态：pending 待解析 / parsed 已解析 / failed 解析失败 |
| created_by | BIGINT | 是 | NULL | 提交人（关联 `user_account.user_id`） |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间（UTC） |
| updated_at | DATETIME(3) | 否 | 当前时间，更新时自动刷新 | 更新时间（UTC） |

- 索引 `idx_source_type_status(source_type, status)`；`created_by` 可选外键 `fk_customer_source_creator → user_account(user_id)`，是否强制由公共负责人确认。

##### 3.2.3 客户关键字段表 `customer_info`

解析后的结构化客户字段，是画像研判的输入；一条来源可产生多条客户记录。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| id | BIGINT | 否 | 自增 | 主键 |
| source_id | BIGINT | 否 | — | 关联来源（外键 → `customer_source.id`） |
| customer_id | BIGINT | 是 | NULL | 归并后关联平台客户主档（外键 → `customer_profile.customer_id`），未归并时为空 |
| full_name | VARCHAR(100) | 是 | NULL | 姓名 |
| gender | VARCHAR(16) | 是 | NULL | 性别 |
| age | INT | 是 | NULL | 年龄 |
| education_level | VARCHAR(32) | 是 | NULL | 学历层次 |
| major | VARCHAR(100) | 是 | NULL | 专业 |
| work_years | INT | 是 | NULL | 工作年限 |
| industry | VARCHAR(64) | 是 | NULL | 行业 |
| position_title | VARCHAR(100) | 是 | NULL | 职位 |
| city | VARCHAR(64) | 是 | NULL | 所在城市 |
| income_level | VARCHAR(32) | 是 | NULL | 收入/薪资层级 |
| target_product_code | VARCHAR(32) | 是 | NULL | 意向产品编码（可空，关联 product.product_code） |
| phone_ciphertext | VARBINARY(512) | 是 | NULL | 加密保存的联系电话（沿用 customer_profile 加密约定） |
| phone_lookup_token | CHAR(64) | 是 | NULL | 标准化手机号的匹配标记，用于受控归并/判重 |
| contact_email | VARCHAR(254) | 是 | NULL | 联系邮箱 |
| raw_fields | JSON | 是 | NULL | 未映射/扩展字段原文 |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间（UTC） |
| updated_at | DATETIME(3) | 否 | 当前时间，更新时自动刷新 | 更新时间（UTC） |
| row_version | INT | 否 | 1 | 并发版本号 |

- 外键：`fk_customer_info_source(source_id) → customer_source(id)`；`fk_customer_info_customer(customer_id) → customer_profile(customer_id)`（可选，归并后回填）。
- 索引：`idx_info_source(source_id)`、`idx_info_phone_token(phone_lookup_token)`、`idx_info_customer(customer_id)`。

**字段命名与加密约定**：联系方式不存明文；`phone_ciphertext` 与 `phone_lookup_token` 与 `customer_profile` 同套加密/匹配方案，保证后续归并可复用同一 token，避免两套去重混用（见 3.3）。

##### 3.2.4 研判规则表 `research_rule`

存《用户画像研判规则》各版本，支持更新与可维护性要求；按产品归属规则。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| id | BIGINT | 否 | 自增 | 主键 |
| product_id | BIGINT | 否 | — | 关联产品（外键 → `product.id`） |
| rule_version | VARCHAR(32) | 否 | — | 规则版本号 |
| rule_content | JSON | 否 | — | 结构化规则内容（命中/未命中条件） |
| rule_description | TEXT | 是 | NULL | 规则说明 |
| is_active | BOOLEAN | 否 | 0 | 是否生效；同产品仅一条生效版本由业务保证 |
| effective_from | DATETIME | 是 | NULL | 生效开始时间 |
| effective_to | DATETIME | 是 | NULL | 生效结束时间（可空） |
| created_by | BIGINT | 是 | NULL | 维护人（关联 `user_account.user_id`） |
| created_at | DATETIME(3) | 否 | 当前时间 | 创建时间（UTC） |
| updated_at | DATETIME(3) | 否 | 当前时间，更新时自动刷新 | 更新时间（UTC） |
| row_version | INT | 否 | 1 | 并发版本号 |

- 外键：`fk_research_rule_product(product_id) → product(id)`。
- 索引：`idx_rule_product_active(product_id, is_active)`、`idx_rule_version(product_id, rule_version)`。
- 生效版本唯一性（同一 product 仅一条 active）建议由业务服务保证，是否加数据库唯一索引由数据库负责人确认。

##### 3.2.5 研判结果表 `research_result`

每条客户 × 每个产品一条结论，命中/未命中均落库，供复核与后续业务使用。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| id | BIGINT | 否 | 自增 | 主键 |
| source_id | BIGINT | 否 | — | 关联来源（外键 → `customer_source.id`） |
| customer_info_id | BIGINT | 否 | — | 关联客户关键字段（外键 → `customer_info.id`） |
| product_id | BIGINT | 否 | — | 关联产品（外键 → `product.id`） |
| rule_version | VARCHAR(32) | 否 | — | 判定所用规则版本 |
| matched | BOOLEAN | 否 | — | 是否命中该产品目标画像 |
| matched_fields | JSON | 是 | NULL | 命中依据字段 |
| unmatched_reasons | JSON | 是 | NULL | 未命中原因 |
| score | DECIMAL(5,2) | 是 | NULL | 规则评分（若规则含评分） |
| created_by | BIGINT | 是 | NULL | 研判人（关联 `user_account.user_id`） |
| created_at | DATETIME(3) | 否 | 当前时间 | 研判时间（UTC） |

- 外键：`fk_result_source(source_id) → customer_source(id)`、`fk_result_info(customer_info_id) → customer_info(id)`、`fk_result_product(product_id) → product(id)`。
- 索引：`idx_result_info(info_id)`、`idx_result_product(product_id)`、`idx_result_matched(product_id, matched)`、`idx_result_source(source_id)`。

### 3.3 字段与表关联冲突的解决

| 冲突点 | 冲突说明 | 解决方式 |
| --- | --- | --- |
| `customer_info` 与 `customer_profile` 字段重叠 | 两者都有姓名、学历、意向国家/产品、联系方式等字段，语义易混 | `customer_info` 定位为「一次来源的结构化快照」，不承担统一客户身份；`customer_profile` 为「平台客户主档」。归并时以 `phone_lookup_token` 受控匹配，命中后回填 `customer_info.customer_id`，不直接覆盖主档字段 |
| 联系方式存储 | `customer_profile.phone_ciphertext` 与研判侧联系方式 | 研判侧复用同一套 `phone_ciphertext` + `phone_lookup_token` 加密/匹配方案，禁止混用两套 token 去重 |
| `product` 与 `course_project` 语义重叠 | 甲方「两个产品」与客服「课程项目」可能为上下级 | 默认独立建表，不强行加外键（避免破坏客服表兼容）。联动时产品→课程的映射由业务层按产品编码/类别完成；后续若确认为严格父子关系，再评估给 `course_project` 增加可空 `product_id` 的增量迁移 |
| `identity_type` 角色冲突 | sgt.md 建议新增「研判人员/复核人员」，与 `user_account` CHECK（仅 admin/employee/customer/student）冲突 | 不新增 `identity_type` 取值；研判/复核通过 `employee.role_codes` 细分（见 4.2），权限挂在 `access_control.yaml` 的 `customer.*` 上，业务层再按角色代码区分数据范围 |
| `created_by` 外键 | 客户研判表需记录提交/研判人 | 关联 `user_account.user_id`；匿名访客不进入研判（研判为受保护内部能力），无访客记账问题 |

### 3.4 表间关联关系（ER 口径）

```text
user_account ──1:N── customer_source (created_by，可选)
user_account ──1:N── research_rule (created_by，可选)
user_account ──1:N── research_result (created_by，可选)

customer_source 1:N customer_info (source_id)
customer_info   N:1 customer_profile (customer_id，可空，归并后回填)
customer_info   1:N research_result (customer_info_id，每产品一条)
product         1:N research_rule (product_id)
product         1:N research_result (product_id)

—— 既有关系（主文档已列，保持不变）——
user_account 1:0..1 employee / customer_profile / student_profile
org_department 1:N employee / customer_profile / student_profile
employee 1:N customer_profile (顾问)
chat_session 1:N chat_message (session_id)
lecture_event 1:N event_signup (event_id)
```

关键闭合：客户研判五表通过 `source_id` 串起「来源 → 字段 → 结果」，通过可空 `customer_info.customer_id` 与平台客户主档衔接，通过 `product` 承接两个产品的规则与结论。客服报名 `event_signup` 与客户研判无直接外键，联动通过业务层把报名留资作为 `customer_source` 文本来源接入（见 4.4）。

---

## 四、功能联动设计与调用流程

### 4.1 三模块功能梳理

| 模块 | 核心功能 | 对外接口 | 复用的公共能力 |
| --- | --- | --- | --- |
| 公共基础能力 | 登录认证、逐接口鉴权、日志、统一返回、Dify HTTP、数据库会话、配置 | 3 个 auth 接口 | —（自身提供） |
| 客服 Agent | 咨询、课程/活动查询、报名、FAQ、会话消息 | 6 个 agent 接口（匿名） | get_db、日志、统一返回、Dify HTTP、配置 |
| 客户信息研判 | 信息接入、多格式解析、关键字段提取、画像研判、结果输出、规则维护 | 8 个 customer 接口（受保护） | JWT 鉴权、get_db、日志、统一返回、Dify HTTP（可选）、配置 |

### 4.2 权限与鉴权联动（identity_type 冲突解决）

客户研判为内部受保护能力，接入公共 JWT 与逐接口鉴权，但不新增身份类型，保证向后兼容：

1. `user_account.identity_type` 仍为 admin / employee / customer / student，CHECK 约束不变。
2. `app/access_control.yaml` 新增客户研判权限标识，并按身份授权：
   - `admin`：追加 `customer.source.*`、`customer.judge.*`、`customer.result.*`、`customer.rule.*`（当前 admin 仅 `admin.dashboard`，需在 YAML 显式补充，不隐含拥有）。
   - `employee`：不把 `customer.*` 直接授给全部员工；由业务服务结合 `employee.role_codes` 细分——`analyst`（研判人员）可用 `customer.source.create`、`customer.source.parse`、`customer.judge.create`、`customer.result.read`；`reviewer`（复核人员）可用 `customer.result.read`、`customer.rule.read`。
   - `customer` / `student`：不新增研判权限（访客/客户不直接研判）。
3. 每个客户研判接口用 `Depends(require_permission("customer.xxx"))` 声明权限；公共鉴权先验证 JWT、映射权限，业务服务再按 `role_codes` 校验 analyst/reviewer 的具体范围。
4. 客服六个接口保持匿名开放，不受 `customer.*` 权限影响。

**权限标识清单（新增）**：`customer.source.create`、`customer.source.parse`、`customer.judge.create`、`customer.judge.batch`、`customer.result.read`、`customer.rule.read`、`customer.rule.manage`。

### 4.3 客户研判主线调用流程

```text
前端/业务 ──POST /api/v1/customer/sources──▶ 鉴权(customer.source.create)
                                              └▶ customer_service 写入 customer_source(status=pending)
                                                  └▶ 返回 source_id
前端/业务 ──POST /api/v1/customer/sources/{id}/parse──▶ 鉴权(customer.source.parse)
                                                        └▶ parser 按 source_type 分派(text/pdf/excel) → 归一化文本
                                                           └▶ extractor 提取关键字段（可选走 clients/extract_dify.py → 公共 DifyHttpClient）
                                                              └▶ 写入 customer_info，回写 customer_source(status=parsed)
                                                                 └▶ 返回关键字段
前端/业务 ──POST /api/v1/customer/judge──▶ 鉴权(customer.judge.create)
                                          └▶ judge_service 加载 research_rule(该产品 is_active 生效版本)
                                             └▶ 逐条规则比对 customer_info 关键字段
                                                └▶ 按 product 分别产出 matched/matched_fields/unmatched_reasons
                                                   └▶ 写入 research_result（每客户×每产品一条）
                                                      └▶ 返回命中结论（命中/未命中均为正常结果，不走异常分支）
前端/业务 ──GET /api/v1/customer/results/{id}──▶ 鉴权(customer.result.read) └▶ 返回结构化结论
```

批量研判 `customer/judge/batch` 按来源范围批量执行，逐条走单条研判逻辑并汇总成功/失败数。规则维护 `GET/PUT /api/v1/customer/rules` 由 `customer.rule.read` / `customer.rule.manage` 控制，更新走新版本号、旧版本保留，满足可维护性。

### 4.4 客服 ↔ 客户研判联动

客服是获客入口，客户研判是筛选/画像入口，两者通过业务层串联，不改动客服既有接口契约：

1. **留资/报名进入研判**：访客在客服报名（`event_signup`）或咨询留下的姓名、手机号、意向等信息，业务层可将其组装为文本来源，作为 `customer_source(source_type=text)` 接入研判流程（可选，需产品确认收集用途与负责人）。
2. **研判结果反哺推荐**：客户研判命中某产品后，可引导前端复用客服 `agent/courses`（`course_project` 上架课程）展示该产品下课程；模型只生成话术与动作，课程列表以数据库为准。产品→课程的映射由业务层完成，不直接改 `course_project` 结构。
3. **报名与研判共享客户联系判重**：`event_signup.customer_phone` 与 `customer_info.phone_lookup_token` 如需归并，按同一套匹配 token 受控处理，不自动合并同号客户。

### 4.5 客户研判 ↔ 客户主档联动

研判命中后，可把结构化客户信息归并为平台客户线索，衔接既有销售/跟进流程：

1. `customer_info` 命中产品后，业务层调用共享客户创建/匹配服务，匹配 `customer_profile`（按 `phone_lookup_token` 提示重复候选）。
2. 新客户创建 `customer_profile` 时：`source_channel='研判'`、`source_reference=customer_info.id` 或 `research_result.id`、`status='new'`，`employee_id` 待分派为空。
3. 匹配到既有客户时，回填 `customer_info.customer_id`，不覆盖主档已有字段；`customer_profile` 的 `status`、`last_followup_at` 由客户模块业务服务维护。
4. 归并受控：仅凭号码提示候选，不自动合并；需约定确认、去重与归属后再扩展业务服务（与主文档第八章「访客留资转客户线索」口径一致）。

---

## 五、合并步骤与注意事项

### 5.1 分阶段合并步骤

| 步骤 | 动作 | 完成标准与证据 |
| --- | --- | --- |
| 0. 锁定版本 | 记录三方仓库/分支、提交号、工作区改动、配置字段及数据库版本 | 每份文件有来源、负责人与处理结论；保留可回退版本 |
| 1. 文件盘点 | 按第二章目录树逐路径核对公共、客服、客户研判及待交付资产 | 形成一致/双方修改/独有/缺失清单 |
| 2. 合并公共契约 | 合并 main.py、config.py、database.py、access_control.yaml、core/*、schemas/auth.py | 公共组件只一套；客服匿名与公共受保护接口均不被破坏；新增 `customer.*` 权限有声明 |
| 3. 接入客户研判 | 合并 api/customer.py、services/customer_*.py、parser/extractor/judge、models 五表、schemas/customer.py | 服务启动无缺失 import，OpenAPI 可见 3 公共 + 6 客服 + 8 研判预期接口 |
| 4. 数据库准备 | 按第三章核对目标库，新增五表走增量建表 | 16 张相关表定义与实际差异清楚；无破坏性全量重建 |
| 5. 配置与环境 | 合并 JWT、Dify（客服 + 客户研判抽取）配置；真实 Key 不入文档 | 仅启用已配置功能，缺配置给出明确错误 |
| 6. 按变更验证 | 覆盖公共认证、客服接口、客户研判接口、并发与归并检查 | 第五章验收项逐项有证据 |
| 7. 条件迁移 | 仅存在同名表/跨副本数据时执行 5.2；否则不迁移存量 | 记录数、关系、切换点验证一致，可回滚 |
| 8. 归档 | 记录合并提交、配置模板、迁移脚本版本及验收结果 | 已实现/已验证/待办清晰 |

### 5.2 数据迁移方案

客户研判五表为新增表，优先「增量建表」，不触碰既有数据：

| 实际情况 | 处理方式 |
| --- | --- |
| 目标库无客户研判五表 | 用核对过的建表语句新增五表；无数据迁移 |
| 目标库已有同名表（另一副本） | 先比对字段/索引/约束，用增量迁移对齐，不执行含 DROP 的重建 |
| 需要跨副本归并客户数据 | 先建立「研判来源 → 客户主档」映射，按 `phone_lookup_token` 受控匹配；不按统一 ID 偏移替代关系核对 |
| 现有 11 表 | 一律不动；客服与公共表结构、索引、外键、CHECK 保持原样 |
| 电话加密/匹配方案若变更 | 由受控流程兼容旧密文并重建匹配值，不混用两套 token；无可靠明文条件时保留隔离数据并记录待处理 |

**回滚**：新增表可通过删除新增表（确认无引用后）回滚；已回填 `customer_info.customer_id` 或已创建 `customer_profile` 的归并动作，先停写、记录增量再对账回退，不直接恢复旧备份丢弃新记录。迁移不撤销已发生的外部写入/通知（本项目当前无此类副作用）。

### 5.3 向后兼容要求

| 项目 | 保留规则 | 必须核验 |
| --- | --- | --- |
| 公共三个接口 | 路径、登录返回、当前账号语义不变 | 错误格式若统一改变需同步调用方 |
| 客服六个接口 | 请求/响应字段、匿名开放、动作语义不变 | 现有前端不带 JWT 仍可咨询和报名 |
| `user_account` 及关联表 | identity_type、CHECK、唯一键、外键不变 | 不新增身份取值；客户研判权限走 YAML + role_codes |
| 客服六表 | 字段、索引、外键、状态式去重不变 | `event_signup` 不引入新唯一约束 |
| JWT | 算法、密钥、有效期、sub 账号映射不变 | 旧 Token 语义不因新增权限改变 |
| Dify | 公共 HTTP 工具契约、客服场景结果契约不变 | 客户研判抽取为独立应用/Key，不影响客服应用 |

### 5.4 风险与注意事项

1. **身份不得新增**：把研判/复核写进 `identity_type` 会破坏 CHECK 与存量账号；必须用 `employee.role_codes` 细分，否则回滚成本高。
2. **联系方式必须同套加密**：`customer_info` 与 `customer_profile` 若用两套 token，归并会失效；禁止明文存手机号。
3. **规则是判定权威**：研判严格依据《用户画像研判规则》，不依赖大模型输出；Dify 仅辅助 PDF/非结构化字段抽取，且需校验工作流业务状态，不能只凭 HTTP 200 判定成功。
4. **产品 vs 课程不强行外键**：先业务层映射，避免破坏 `course_project` 兼容；确认为父子关系后再做可空外键增量迁移。
5. **匿名与受保护边界**：客服匿名开放，客户研判必须登录鉴权；不得把访客 `chat_session.user_id` 当作平台身份用于研判鉴权。
6. **待交付资产不虚构**：客服 DSL、知识库、种子/联调脚本与客户研判抽取 DSL 等标记为「待交付/可选」，不以目录树认定已存在。
7. **字段口径待冻结**：客户研判五表字段为设计口径，类型/约束/索引需甲方规则与团队 DDL 确定后再落地，避免提前建表后返工。

---

## 六、合并验收要点

- 公共登录成功取得 JWT；受保护接口分别拦截缺失、无效/过期 Token 与无权限请求，错误按约定返回。
- 客服六个接口不带 Token 仍可访问；请求/响应与现有前端兼容。
- 客户研判八个接口需登录并具备对应 `customer.*` 权限；研判/复核通过 `employee.role_codes` 区分，管理员不隐含拥有全部 `customer.*`。
- 客户信息接入后能按 text/pdf/excel 正确解析，关键字段提取完整；研判结果严格依据规则、命中/未命中均结构化落库，批量研判逐条汇总。
- 规则可版本化更新，旧版本保留，生效版本唯一；更新不影响已生成的 `research_result`（记录 rule_version）。
- 归并链路可追溯：`customer_source → customer_info → research_result`，`customer_info.customer_id` 回填正确，同号匹配仅提示候选不自动合并。
- 迁移可回滚：新增表建/删可逆，归并动作有对账与回退方案；存量 11 表结构与数据无变化。
- 日志、响应、数据库会话、配置与 Dify 公共传输调整后，客服、客户研判及既有业务（学生/报告等已启用调用方）通过对应回归，不引入未交付模块的导入失败。

以上为执行检查项，本次文档完善未运行这些功能验收。
