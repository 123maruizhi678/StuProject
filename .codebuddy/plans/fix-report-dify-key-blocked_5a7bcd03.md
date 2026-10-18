---
name: fix-report-dify-key-blocked
overview: 修复智能报告生成全部失败的问题：根因是 scripts/dev.mjs 启动后端时清空 REPORT_DIFY_API_KEY（团队级外联开关），已由失败原因截图确认。方案是在 .12 机器上改用“手动起后端（正常读取 .env 密钥）+ npm run dev 复用已运行后端”的方式启动，零共享文件改动；随后验证生成成功，并核查截图暴露的“统计记录数=0”数据就绪问题。
todos:
  - id: verify-key
    content: 校验 app-C0NU8 密钥在 .12 Dify 的有效性（GET /v1/parameters）
    status: completed
  - id: start-backend
    content: 在 .12 用 SST 环境手动启动 uvicorn（0.0.0.0:8000）并确认 /health
    status: completed
    dependencies:
      - verify-key
  - id: rerun-dev
    content: 在 .12 复跑 npm run dev 使其复用已运行后端（vite 5173）
    status: completed
    dependencies:
      - start-backend
  - id: generate-verify
    content: 用新时间窗生成一份报告，验证状态转 success 且正文引用真实指标
    status: completed
    dependencies:
      - rerun-dev
  - id: data-check
    content: 核查 .12 MySQL 上游六表是否有数据（统计记录数=0 问题）
    status: completed
  - id: frontend-retest
    content: 硬刷新后复测下拉框、中文标签与时间显示（完整到秒）
    status: completed
    dependencies:
      - rerun-dev
  - id: propose-to-lead
    content: 向组长提案 dev.mjs 外联开关处理（方案 A 或 C），本次不动共享脚本
    status: completed
    dependencies:
      - generate-verify
---

## 问题确认（截图实证）
智能报告模块所有报告生成失败，详情页失败原因为：`ReportDifyError: 未配置报告生成 Dify 工作流 API Key（REPORT_DIFY_API_KEY）`。根因已在代码中双重确认：`scripts/dev.mjs`（组长维护的 dev 启动脚本）在未设置 `STUPROJECT_ENABLE_EXTERNAL=1` 时，会把 `REPORT_DIFY_API_KEY` 等全部 Dify 密钥清空后再启动后端（注释：“当前验收范围不配置外部服务”）。报告客户端在密钥缺失时按契约直接失败，行为正确，问题在启动方式而非代码。

## 附带发现（截图）
- 报告编号 2 的指标快照时间已生成、统计记录数=0：取数链路正常（上游表存在），失败发生在 Dify 调用；修复密钥后报告会转 success，但指标可能全为 0/不可用，需确认 .12 的 MySQL 上游业务数据是否就绪。
- 详情页时间显示完整（2026-10-15T16:00:00.00），此前“只显示到日”应为静态预览页或浏览器缓存，需复测确认。

## 修复目标
在不改动组长共享脚本、不影响其他模块外联策略的前提下，让 .12 环境（http://192.168.5.12:8000 后端 + :5173 前端）的报告生成链路恢复可用并验证成功；顺带完成数据就绪度核查与前端显示复测。

## 方案选型（三选项，推荐 B）

| 选项 | 做法 | 评估 |
|---|---|---|
| A | `STUPROJECT_ENABLE_EXTERNAL=1` 启 dev.mjs | 恢复所有模块 Dify 密钥，推翻组长“当前验收范围不配置外部服务”的统一决策，需团队级确认，本次不做 |
| B | 手动起后端（正常读 .env）+ npm run dev 复用 | dev.mjs 的启动逻辑 `if (!await health()) { if (!await backendPortOpen()) launch(...) }` 会检测到 8000 已有健康后端并跳过自起——清空逻辑只作用于它自己 spawn 的后端。零共享文件改动、不影响其他模块，采用 |
| C | 改 dev.mjs 清空名单剔除 REPORT_DIFY_API_KEY | 1 行精准但动组长共享文件，列为向组长提案的后续项，本次不改 |

## 关键执行细节
1. **解释器对齐**：dev.mjs 使用 SST conda 环境（候选顺序：`$CONDA_PREFIX/python.exe`、`~/anaconda3/envs/SST/python.exe`、`D:/anaconda3/envs/SST/python.exe`），.12 上手动起后端须用同一解释器，避免依赖缺失。
2. **密钥归属**：`.env`（HEAD）中 `REPORT_DIFY_API_KEY="app-C0NU8tGFo1ntY8nreh486IbW"` 与 .12 的 Dify（80 端口）对应；本机 Dify 的 Key 是另一把，不可通用。启动前先用只读 `GET http://192.168.5.12/v1/parameters`（Bearer 该 Key）校验：200=有效且为工作流类应用；401/404 需先在 .12 的 Dify 发布工作流应用并更换 Key。
3. **启动顺序**：先停 dev.mjs（Ctrl+C）→ 手动 uvicorn（`--host 0.0.0.0 --port 8000`，保证 LAN 可达）→ /health 确认 → 再 `npm run dev`（health 检查通过，跳过自起后端，只起 vite 5173）。
4. **失败记录重试语义（041 规定）**：同参数（同 report_code + 同窗口）会命中同一业务键，generate 返回 `reused=true` 的原失败记录、不会重新调模型（failed 不自动重发）。因此验证修复必须换一个**新时间窗**（如显式选另一天，或用默认窗口次日再试），不能对报告 #2 原样重试。
5. **数据就绪**：统计记录数=0 说明窗口内无上游数据；修复后若指标全 0/不可用，需在 .12 的 MySQL 核查 `employee_daily_report`、`service_ticket`、`customer_profile`、`customer_followup`、`mental_health_profile`、`mental_warning` 是否有数据，或导入测试数据。
6. **机器边界**：本机（192.168.5.15）与 .12 是两台机器，服务重启动作由用户在 .12 执行，本机仅提供命令与验证标准；本机现有 uvicorn（127.0.0.1:8000）只用于联调，不参与本次修复。
