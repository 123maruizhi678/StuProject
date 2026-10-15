# 客服Agent 接口与身份权限清单

> 本文档基于《客服Agent接口鉴权方案》整理，汇总客服Agent 模块的**全部接口**、系统涉及的**全部身份**，以及**每个身份可调用哪些接口**的权限关系。
> 范围：客服Agent 模块（6 个接口）。当前接口均**无鉴权（匿名直连）**，下表为「现状 / 目标态」对照。

---

## 一、接口清单（全部）

| 序号 | 方法 | 路径 | 说明 | 访问级别（目标态） |
|:---:|:---|:---|:---|:---:|
| 1 | POST | `/api/v1/agent/chat` | 客服对话（含会话/消息落库） | public |
| 2 | GET | `/api/v1/agent/events` | 活动列表 | public |
| 3 | GET | `/api/v1/agent/events/{id}` | 活动详情 | public |
| 4 | POST | `/api/v1/agent/events/signup` | 活动报名（写库 + 采集手机号） | public（可升级 visitor） |
| 5 | GET | `/api/v1/agent/courses` | 课程列表 | public |
| 6 | GET | `/api/v1/agent/faq` | FAQ 兜底查询 | public |

---

## 二、身份清单（客服Agent）

| 身份 | type | role | 来源 | 主要使用模块 |
|:---|:---|:---|:---|:---|
| 员工 | `employee` | `advisor` | 企业登录后签发 | 企业智能助手、智能报告、后台管理 |
| 学生 | `student` | `student` | 学生登录后签发 | 学生智能助手 |
| 访客/潜在客户 | `visitor` | `anonymous` | 匿名或留资（首访后端签发匿名 token） | **客服Agent** |

认证机制：统一采用 **JWT（Bearer Token）**，`Authorization: Bearer <token>` 传递，token 内含 `type` / `role` / `scopes` 字段。

---

## 三、身份 × 接口 权限矩阵

> 说明：客服Agent 在统一鉴权中为 **`public` 级别（公开访问，不强制身份认证）**，防护重点是「限流 + 防刷 + 敏感数据脱敏」。
> 因此从「能否访问」角度，**任何身份均可访问全部 6 个接口（无需登录）**；但从「业务目标与授权 scope」角度，各身份的归属不同。

| 接口 | 访客/潜在客户（visitor） | 员工（employee） | 学生（student） |
|:---|:---:|:---:|:---:|
| POST `/agent/chat` | ✅ 主用（`agent:chat`） | ✅ 可访问（public） | ✅ 可访问（public） |
| GET `/agent/events` | ✅ 主用（`agent:events`） | ✅ 可访问（public） | ✅ 可访问（public） |
| GET `/agent/events/{id}` | ✅ 主用（`agent:events:read`） | ✅ 可访问（public） | ✅ 可访问（public） |
| POST `/agent/events/signup` | ✅ 主用（`agent:signup`，强限流 + 防重） | ✅ 可访问（public） | ✅ 可访问（public） |
| GET `/agent/courses` | ✅ 主用（`agent:courses`） | ✅ 可访问（public） | ✅ 可访问（public） |
| GET `/agent/faq` | ✅ 主用（`agent:faq`） | ✅ 可访问（public） | ✅ 可访问（public） |

**逐身份解读：**

### 1. 访客/潜在客户（visitor）
- **归属模块**：客服Agent（本模块目标用户）。
- **持有 scope**：`agent:*`（覆盖全部 6 个接口）。
- **可调用接口**：全部 6 个。
- **认证**：不强制登录；首访由后端签发匿名 `visitor` token，绑定 `session_id`，用于会话关联、限流计数与防刷审计。
- **特殊约束**：`signup` 接口风险最高，即使访客匿名访问也须接受「IP 限流 + 幂等（event_id + customer_phone 唯一约束）+ 手机号格式校验 +（可选）验证码」。

### 2. 员工（employee）
- **归属模块**：企业智能助手、智能报告、后台管理（非客服Agent）。
- **持有 scope**：以 `enterprise:*` 为主（企业模块授权）。
- **可调用接口**：因客服Agent 为 `public`，员工身份**技术上可访问全部 6 个接口**，但**非业务目标用户**；其主用接口不在本清单内。
- **认证**：登录后签发含真实身份的 JWT（authenticated 级别）。

### 3. 学生（student）
- **归属模块**：学生智能助手（非客服Agent）。
- **持有 scope**：以 `student:*` 为主（学生模块授权）。
- **可调用接口**：因客服Agent 为 `public`，学生身份**技术上可访问全部 6 个接口**，但**非业务目标用户**；其主用接口不在本清单内。
- **认证**：登录后签发含真实身份的 JWT（authenticated 级别）。

---
