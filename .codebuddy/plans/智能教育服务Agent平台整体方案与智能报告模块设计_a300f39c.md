---
name: 智能教育服务Agent平台整体方案与智能报告模块设计
overview: 基于《业务文档》目录下全部文档的交叉比对，输出面向留学机构的智能教育服务 Agent 平台整体方案，并重点产出"智能报告"模块的完整设计方案（含目标、功能范围、输入输出、关键流程、数据来源、处理逻辑、异常边界、依赖、性能安全、验收标准、迭代计划）。
todos:
  - id: analyze-overall
    content: 综合01/02需求文档，输出平台整体目标、五大模块业务场景与需求全景
    status: completed
  - id: report-scope
    content: 结合03/04/05/06文档，明确智能报告模块目标、功能范围与输入输出
    status: completed
    dependencies:
      - analyze-overall
  - id: report-flow
    content: 设计五类报告的关键流程、数据来源与处理逻辑
    status: completed
    dependencies:
      - report-scope
  - id: report-edge
    content: 梳理智能报告异常与边界情况、模块依赖关系
    status: completed
    dependencies:
      - report-flow
  - id: report-quality
    content: 制定性能与安全要求、验收标准及迭代计划
    status: completed
    dependencies:
      - report-edge
  - id: finalize-doc
    content: 交叉比对全部文档，自检一致性并整合输出最终整体方案文档
    status: completed
    dependencies:
      - report-scope
      - report-flow
      - report-edge
      - report-quality
---

## 用户需求
读取 `业务文档` 目录下全部文件（01需求拆解、02需求文档、03开发设计、04接口设计、05数据库设计、06开发文档及根目录 StuProject_开发文档.md），交叉比对后输出一份整体方案，并重点给出"智能报告"模块设计方案。方案须覆盖：模块目标、功能范围、输入与输出、关键流程、数据来源、处理逻辑、异常与边界情况、依赖关系、性能与安全要求、验收标准、迭代计划共 11 项，确保结论与文档内容一致。

## 交付物概述
一份结构化方案文档，分为两部分：
1. 平台整体方案：面向留学机构的智能教育服务 Agent 平台的整体目标、核心业务场景与需实现的需求。
2. 智能报告模块设计：五类报告（全域客户经营分析、员工日报日/周汇总、学生心理健康周报、投诉处理周报）的完整设计方案。

## 核心内容要点
- 整体方案：五大模块（客户研判、客服Agent、企业智能助手、学生智能助手、智能报告）的职责、业务场景与 AI 能力，以及前端 + FastAPI + 本地 Dify + 本地 MySQL 四层架构。
- 智能报告：五类报告的数据来源、指标先由确定性 SQL 计算再交由 AI 摘要的处理原则、NL2SQL 聚合链路、手动/定时/事件三类触发方式、报告配置与生成记录、心理数据脱敏与权限隔离。
- 交叉比对结论：报告类型枚举不足（仅 daily/weekly 无法表达五类报告）、全域客户分析数据缺口（缺成交/流失/跟进历史字段）、投诉双表事实源、指标口径未统一、智能报告需求文档结构不完整等差异，须在方案中明确并给出建议。
