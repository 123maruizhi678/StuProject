# 客服Agent 接口鉴权接入方案

> 范围：客服Agent 模块 6 个接口（已实现）。
> 目的：为后续「全系统统一鉴权」预留接入点，明确客服Agent 各接口的访问级别与防护措施。
> 现状：接口已可运行，当前**无任何鉴权**，任何请求均可直接访问。

---

## 一、接口现状（无鉴权）

| 方法 | 路径 | 说明 | 当前访问 |
|:---|:---|:---|:---:|
| POST | `/api/v1/agent/chat` | 客服对话（含会话/消息落库） | 匿名直连 |
| GET | `/api/v1/agent/events` | 活动列表 | 匿名直连 |
| GET | `/api/v1/agent/events/{id}` | 活动详情 | 匿名直连 |
| POST | `/api/v1/agent/events/signup` | 活动报名（写库） | 匿名直连 |
| GET | `/api/v1/agent/courses` | 课程列表 | 匿名直连 |
| GET | `/api/v1/agent/faq` | FAQ 兜底查询 | 匿名直连 |

---

## 二、统一鉴权总体设计（全系统视角）

### 2.1 身份主体

系统内存在三类主体，统一抽象为一个 `Principal`（身份主体）模型：

| 主体 | 来源 | 主要模块 |
|:---|:---|:---|
| 员工 | 企业登录 | 企业智能助手、智能报告、后台管理 |
| 学生 | 学生登录 | 学生智能助手 |
| **访客/潜在客户** | **匿名或留资** | **客服Agent** |

### 2.2 认证机制：JWT（Bearer Token）

统一采用 **JWT** 做认证凭证，`Authorization: Bearer <token>` 传递。

```json
{
  "sub": "主体唯一ID（访客可用匿名标识）",
  "type": "employee | student | visitor",
  "role": "advisor | student | anonymous",
  "scopes": ["agent:chat", "agent:signup", "enterprise:*"],
  "exp": 1730000000,
  "iat": 1729996400
}
```

- `type` 区分主体大类；`role` 细分角色；`scopes` 做细粒度接口权限。
- 员工/学生：登录后签发（含真实身份 + 权限）。
- 访客：**不强制登录**。首访时由后端签发一个 `visitor` 匿名 token，绑定 `session_id`，用于会话关联、限流计数与防刷审计。

### 2.3 访问级别

| 级别 | 含义 | 适用 |
|:---|:---|:---|
| `public` | 无需认证，但统一走限流与审计 | 客服Agent 全部接口 |
| `visitor` | 需访客匿名 token | 客服Agent 报名/留资（可选增强） |
| `authenticated` | 需登录（员工/学生） | 企业/学生/报告模块 |

> 关键结论：客服Agent 在统一鉴权里是 **`public` 级别（公开访问）**，**不是**每个接口都要登录。它的防护重点在「限流 + 防刷 + 敏感数据脱敏」，而非身份认证。

### 2.4 统一接入点

- **全局中间件**：解析 `Authorization` 头 → 注入 `Principal` 到请求上下文；同时做**全局限流**。
- **依赖注入**：各接口用 `Depends(...)` 声明自身访问级别。
  - `require_public()`   → 公开接口（客服Agent）
  - `require_visitor()`  → 需访客 token
  - `require_roles("advisor", ...)` → 员工/学生模块

---

## 三、客服Agent 接口鉴权矩阵（目标态）

| 接口 | 访问级别 | 认证 | 防护重点 |
|:---|:---:|:---|:---|
| POST `/agent/chat` | public | 否 | 限流（防刷 LLM 成本）、会话落库 |
| GET `/agent/events` | public | 否 | 公开信息，正常限流 |
| GET `/agent/events/{id}` | public | 否 | 公开信息 |
| POST `/agent/events/signup` | public（可升级 visitor） | 否（可选 visitor token） | **强限流 + 防重 + 手机号校验** |
| GET `/agent/courses` | public | 否 | 公开信息 |
| GET `/agent/faq` | public | 否 | 公开信息 |

说明：
- 前 5 个接口维持匿名公开，降低访客咨询门槛（业务目标就是 7×24 无人值守）。
- `signup` 是唯一的「写库 + 采集个人信息」接口，风险最高，单独加强：IP 限流、幂等（已有 `event_id + customer_phone` 唯一约束）、手机号格式校验、可选验证码；后续若接入 CRM/客户统一管理，可升级为 `visitor` 或 `authenticated`。

---

## 四、技术实现要点

### 4.1 新增 `app/core/security.py`

```python
# 核心能力（示意）
- create_token(principal) -> str        # 签发 JWT
- decode_token(token) -> Principal      # 解析校验
- get_current_principal(auth_header, allow_anonymous) -> Principal  # 依赖
- require_roles(*roles)                 # 角色鉴权依赖
```

统一返回约定：鉴权失败返回 HTTP 401 + body `{"code": 401, "message": "未授权", "data": null}`（沿用 `ResultCode.UNAUTHORIZED`，需新增一个 401 handler，见 5.3）。

### 4.2 限流与防刷

| 维度 | 建议策略 |
|:---|:---|
| 全局 | IP 维度，如 120 req/min |
| `/agent/chat` | 更严，如 20 req/min/IP（防止刷 LLM 调用成本） |
| `/agent/events/signup` | 最严，如 5 req/min/IP + 幂等键 + 手机号校验（可选图形验证码） |

实现可选 `slowapi`（基于 limits），或自写基于内存/Redis 的滑动窗口中间件。多实例部署时用 Redis 集中计数。

### 4.3 敏感数据与审计

- 报名接口**响应不返回**手机号明文，仅返回 `signup_id`（当前已如此）。
- 报名/对话落库含手机号，DB 侧后续可加密存储（`customer_phone` 密文 + 检索 token），与统一「客户数据安全存储」要求对齐。
- 关键写操作接入操作日志（复用后续 `operation_log` 表思路），记录 IP、主体、时间、动作。

---

## 五、代码对接点（当前 → 目标）

| 文件 | 改动 |
|:---|:---|
| `app/core/security.py` | **新增**：JWT 编解码、`Principal`、鉴权依赖、401 handler |
| `app/config.py` | 新增 `JWT_SECRET_KEY`、`JWT_EXPIRE_MINUTES`、`RATE_LIMIT_*` 等配置 |
| `app/main.py` | 注册限流中间件 + 统一鉴权中间件 |
| `app/api/agent.py` | 各接口加 `Depends(require_public())`；`signup` 加限流依赖 |
| `.env` | 新增 `JWT_SECRET_KEY=...`、限流参数 |
| `requirements.txt` | 新增 `PyJWT`（或 `python-jose`）、限流库 |

> 说明：本阶段**仅落文档、不急于改代码**。真正改造时先做「统一鉴权基础设施」（security.py + 中间件），再把客服Agent 标记为 `public` 一次性接入；内部模块（企业/学生/报告）按各自模块开发进度分别接入。

---

## 六、落地阶段（渐进式）

| 阶段 | 内容 | 产出 |
|:---|:---|:---|
| 0 | 现状：接口无鉴权，仅靠数据库唯一约束防重 | 已完成 |
| 1 | 建统一鉴权基础设施：JWT 工具 + Principal + 中间件 + 401 handler | `app/core/security.py` |
| 2 | 客服Agent 接口接入 `public` 级别 + 全局限流 | agent 接口可安全暴露 |
| 3 | `signup` 加强：限流 + 手机号校验（+ 可选访客 token/验证码） | 防刷闭环 |
| 4 | 员工/学生/报告模块接入 `authenticated` 鉴权 | 全系统统一 |
| 5 | 敏感数据加密存储 + 操作审计 | 合规收尾 |

---

## 七、安全清单

- [ ] JWT 密钥通过 `.env` 注入，不入库、不提交仓库
- [ ] 鉴权失败统一 HTTP 401 + `{code:401}`
- [ ] 所有公开接口接入限流；`chat`/`signup` 单独收紧
- [ ] `signup` 手机号格式校验 + 幂等（已有唯一约束兜底）
- [ ] 报名/留资手机号不在响应中明文返回
- [ ] 写操作记录审计（主体 + IP + 时间 + 动作）
- [ ] 匿名访客 token 与 `session_id` 关联，支持留资后升级为真实身份
