# 智能报告模块 API 接口方案

日期：2026-10-16。
本方案说明智能报告模块对外的 HTTP 接口，以及与其他模块/共享能力的调用关系。
取代《接口设计文档.txt》第六章的旧版报告接口（旧版 `report_type` 仅 daily/weekly，无法表达五类报告）。

---

## 一、模块定位

智能报告模块是整个系统的「数据消费末端」：

- 它**不产生业务数据**，而是从其他模块（企业、学生、客户研判、客服）**读数据 → 算指标 → AI 写分析 → 产出报告**。
- 报告最终只给**管理员 / 管理层**看。

因此它的调用关系不对称：

```
谁调我：  只有「管理层看板前端」+「我自己的定时任务」
我调谁：  读 N 个模块的数据 + 依赖一组共享能力
```

```
企业智能助手 ─┐
学生智能助手 ─┼──(共享数据表)──→ 智能报告模块 ──(报告接口)──→ 管理层看板前端
客户研判   ──┤                        ↑
组长/共享能力─┘(NL2SQL、Dify、鉴权)───┘
```

---

## 二、方向一：哪些模块需要调用我的接口

| 调用方 | 调我哪些接口 | 干什么 | 性质 |
|:---|:---|:---|:---|
| **管理层看板前端** | 全部 5 个接口 | 手动点「生成报告」、看报告列表/详情、改报告定时配置 | 主要外部调用方 |
| **报告模块自己的定时任务**（apscheduler） | 不调 HTTP，直接调生成 service | 日报每天、周报每周五自动生成 | 模块内部，不算跨模块 |
| （可选）企业智能助手 | `GET /report/list`、`GET /report/{id}` | 管理层通过企业助手对话调出报告 | 只读，可后续互通 |
| （可选）共享通知服务 | 不回调我，是我生成完去通知它 | 报告完成后推送管理层 | 我调它，不是它调我 |

**关键结论**：业务模块（企业、学生、客服、客户研判）**不调用报告接口**——它们是给报告模块供数据的，不是来读报告的。报告接口只对「管理员角色」开放即可。

---

## 三、方向二：我的接口需要调用哪些模块的接口

### 3.1 走 HTTP 接口调用的（真正的「调用别人接口」）

| 依赖 | 谁提供 | 用途 |
|:---|:---|:---|
| **统一 NL2SQL 查询接口** | 组长 / 共享能力 | 核心。把「聚合本周全员日报」等查询交给它执行并返回结果集。白名单 + 行权限 + 只读，**报告模块不直接拼 SQL 查库** |
| **Dify NL2SQL 工作流** | 共享 AI 能力 | 把自然语言聚合需求转成 SQL |
| **Dify 报告生成工作流** | 共享 AI 能力 | 对**已经算好的数字**写摘要、趋势、归因、建议（严禁让 AI 自己编数字） |
| **认证鉴权服务** | 共享能力 | 每个接口先验 token、判断是否管理员角色 |
| （可选）共享通知服务 | 共享能力 | 报告生成完成后推送管理层 |

### 3.2 通过共享数据表读取的（约定契约，不是 HTTP）

数据都在同一套 MySQL 里，由其他模块写入，报告模块按约定**只读**：

| 数据表 | 来自哪个模块 | 用于生成哪份报告 |
|:---|:---|:---|
| `customer_profile` / `customer_followup` | 企业智能助手 | 全域客户经营分析 |
| `customer_judgement` | 客户研判（**表尚未落地**） | 全域客户经营分析（研判参考） |
| `employee_daily_report` | 企业智能助手 | 员工日报汇总（日/周） |
| `mental_health_profile` / `mental_warning` | 学生智能助手 | 学生心理健康周报 |
| `service_ticket` | 企业 + 学生共享的统一工单 | 投诉处理周报 |

> 注意：这些**不是 HTTP 接口调用**，而是通过组长的 NL2SQL 查询服务去读共享表。
> 跨模块不各写一份数据，一张表只有一个维护人，报告模块只读聚合。

---

## 四、对外的 API 接口清单

统一信封 `{code, message, data}`，`Authorization: Bearer <token>`，仅管理员/管理层角色可访问。

| 方法 | 路径 | 说明 | 谁调用 |
|:---|:---|:---|:---|
| POST | `/api/v1/report/generate` | 手动生成（异步，先返回 `report_record_id` + pending） | 看板前端 |
| GET | `/api/v1/report/{report_record_id}` | 查单份报告（含正文；心理周报匿名） | 看板前端 / 可选企业助手 |
| GET | `/api/v1/report/list` | 分页列表，按 report_code/status 过滤 | 看板前端 |
| GET | `/api/v1/report/configs` | 查 5 类报告的配置 | 看板前端 |
| PUT | `/api/v1/report/configs/{report_code}` | 改名称 / 定时表达式 / 启停 | 看板前端 |

### 4.1 生成报告

`POST /api/v1/report/generate`

请求体：

```json
{
  "report_code": "weekly_report",
  "start_time": "2025-03-17T00:00:00Z",
  "end_time": "2025-03-23T23:59:59Z",
  "timezone": "UTC"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| report_code | 是 | 五类报告代码之一 |
| start_time / end_time | 否 | 统计时间窗；不传时后端按 report_code 周期自动取最近完整周期（日=昨天，周=上周） |
| timezone | 否 | 统计口径时区，默认 UTC |

响应（立即返回，生成走异步任务）：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "report_record_id": 123,
    "idempotency_key": "weekly_report:2025-03-17/2025-03-23:v1",
    "status": "pending"
  }
}
```

说明：

- 生成要经历「取数 → 算指标 → 调 AI」，耗时较长，所以接口只收单并返回任务标识，前端用 `report_record_id` 反复调 4.2 看 `status` 是否变成 success/failed。
- 幂等：相同 `report_code + 时间窗 + 版本` 只生成一次。完全相同的重复请求返回已有记录（code=0 且 `report_record_id` 不变）；同键但内容不同返回 409。

### 4.2 查询单份报告

`GET /api/v1/report/{report_record_id}`

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "report_record_id": 123,
    "report_code": "weekly_report",
    "report_name": "员工日报汇总报告（周）",
    "start_time": "2025-03-17T00:00:00Z",
    "end_time": "2025-03-23T23:59:59Z",
    "timezone": "UTC",
    "data_snapshot_at": "2025-03-23T18:00:12.345Z",
    "report_version": "v1",
    "source_record_count": 87,
    "status": "success",
    "report_content": "……AI 生成的结构化正文……",
    "metric_json": { "提交数": 45, "未提交数": 3 },
    "fail_reason": null,
    "generated_at": "2025-03-23T18:00:15Z"
  }
}
```

脱敏规则：`mental_weekly` 对普通管理员只返回匿名聚合内容，不返回个人明细；个人级明细仅授权页面可见，不在本接口返回。

### 4.3 查询报告列表

`GET /api/v1/report/list?report_code=weekly_report&status=success&page=1&page_size=20`

| 参数 | 说明 |
|---|---|
| report_code | 可选，按报告类型过滤 |
| status | 可选，pending/running/success/failed |
| page / page_size | 分页，page 从 1 开始，默认 1 / 20 |

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 56,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "report_record_id": 123,
        "report_code": "weekly_report",
        "report_name": "员工日报汇总报告（周）",
        "start_time": "2025-03-17T00:00:00Z",
        "end_time": "2025-03-23T23:59:59Z",
        "status": "success",
        "generated_at": "2025-03-23T18:00:15Z"
      }
    ]
  }
}
```

说明：列表不返回 `report_content`（正文大，列表只给元数据）。

### 4.4 查询报告配置

`GET /api/v1/report/configs`

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "report_config_id": 2,
      "report_code": "daily_report",
      "report_name": "员工日报汇总报告（日）",
      "report_period": "day",
      "cron_expr": "0 30 18 * * *",
      "enabled": true,
      "row_version": 3
    },
    {
      "report_config_id": 1,
      "report_code": "customer_overview",
      "report_name": "全域客户经营分析报告",
      "report_period": "week",
      "cron_expr": "0 0 9 * * 5",
      "enabled": true,
      "row_version": 1
    }
  ]
}
```

### 4.5 更新报告配置

`PUT /api/v1/report/configs/{report_code}`

请求体：

```json
{
  "row_version": 3,
  "report_name": "员工日报汇总报告（日）",
  "cron_expr": "0 30 18 * * *",
  "enabled": true
}
```

说明：

- `report_code` 与 `report_period` 是类型枚举，不允许修改；只允许改报告名称、定时表达式、是否启用。
- `row_version` 必填，做乐观锁：请求带的是 4.4 查到的版本，后端 `UPDATE ... WHERE row_version = 传入值`，更新成功则版本 +1；版本不匹配返回 `code=409`（两人同时改，后提交的被拒绝，需重取最新配置再改）。

---

## 五、报告代码枚举

| report_code | 报告名称 | 周期 |
|:---|:---|:---|
| `customer_overview` | 全域客户经营分析报告 | week |
| `daily_report` | 员工日报汇总报告（日） | day |
| `weekly_report` | 员工日报汇总报告（周） | week |
| `mental_weekly` | 学生心理健康周报 | week |
| `complaint_weekly` | 投诉处理周报 | week |

---

## 六、总约定

- 统一信封：HTTP 200 + `{code, message, data}`。
  业务码：0 成功、400 参数错误、401 未登录、403 无权限、404 不存在、409 冲突（幂等/版本）、503 依赖不可用。
- 认证：`Authorization: Bearer <token>`，管理员/管理层角色。
- 时间格式：ISO 8601 带时区（如 `2025-03-23T18:00:00Z`）。库内统一存 UTC，展示由前端转时区。

---

## 七、三个必须记住的依赖风险

1. **投诉数据已统一**：投诉周报只读 `service_ticket`（`after_sales_ticket` 已排除），表结构附录已对齐。
2. **心理周报要脱敏**：查询接口对普通管理员只返回匿名聚合，**不返回学生个人心理明细**。
3. **经营分析排最后**：依赖 `customer_judgement` 表（尚未落地）和成交金额/流失原因等字段（尚缺），按迭代顺序最后做，否则会算出误导人的数字。

**一句话总结**：对外守住「给管理员看报告」这 5 个接口；对内主要依赖「组长的 NL2SQL 查询 + Dify 两个工作流 + 别家交付的共享数据表」。