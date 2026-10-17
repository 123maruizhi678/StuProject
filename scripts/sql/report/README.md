# 智能报告模块 SQL 增量与配置种子说明

本目录登记智能报告模块的数据库增量、种子与回滚边界。报告只读上游，自身新增
数据限于 `report_config` / `report_record` / `report_metric` 三张已部署表，
以及 041 拟新增、尚未部署的 `report_task` 执行任务表。

## 基线

| 资产 | 作用 |
| --- | --- |
| `scripts/sql/all.sql` | 全量结构唯一主基线；报告三表 9+18+10 字段以此为准 |
| `scripts/sql/bk/智能报告/report_module_ddl.sql` | 模块 DDL 受控抽取件；**含 DROP TABLE，不是日常升级脚本** |
| `app/models/report/report.py` | ORM 按基线映射；`REPORT_TABLES` 为三张已部署表 |
| `scripts/report/init_report_tables.py` | 初始化/核对入口；`--dry-run` 打印 DDL，`--check` 核对，`--apply` 建表+种子 |

基线规则：新增需求先形成明确目标差异，再统一修订基线／抽取件／ORM，不能
两份 SQL 独立演化。对已有数据库只使用经审核增量迁移，不运行全量脚本。

## 五条配置种子

与 `all.sql` 中 5 条 INSERT 口径一致；`cron_expr` 为目标调度时刻（含秒六
字段，东八区 `Asia/Shanghai`，17:00 只是触发时刻，不改变统计窗）：

| report_code | report_period | cron_expr | 说明 |
| --- | --- | --- | --- |
| `customer_overview` | week | `0 0 17 * * 5` | 全域客户经营分析报告 |
| `daily_report` | day | `0 0 17 * * *` | 员工日报汇总报告（日） |
| `weekly_report` | week | `0 0 17 * * 5` | 员工日报汇总报告（周） |
| `mental_weekly` | week | `0 0 17 * * 5` | 学生心理健康周报（仅匿名聚合） |
| `complaint_weekly` | week | `0 0 17 * * 5` | 投诉处理周报 |

存量库中旧的 18:30／09:00 种子按受控增量 UPDATE 至 17:00 并按配置版本规则
递增 `row_version`，保留五类 `report_code`，不 DROP 重建；`init_report_tables.py`
只在 `report_config` 为空时写种子，不覆盖已修改的配置。

## 拟新增：report_task（041，尚未部署）

执行所有权以任务为准的持久任务表（`report_record.status` 仍为对外四状态投影）：

```text
report_task(
  report_task_id   BIGINT PK 自增,
  report_record_id BIGINT 非空 唯一 FK→report_record RESTRICT,
  report_code      VARCHAR(64) utf8mb4_bin,
  idempotency_key  VARCHAR(128) utf8mb4_bin 唯一,
  status           VARCHAR(32) utf8mb4_bin pending/running/success/failed,
  lease_owner      VARCHAR(128) NULL,
  lease_expires_at DATETIME(3) NULL,
  attempt_count    INT 默认 0（非负）,
  last_error       TEXT NULL（脱敏）,
  model_checkpoint JSON NULL（受控调用阶段/可信 workflow_run_id/受保护回执引用，
                     不写 Key 或原业务文本）,
  created_at/updated_at DATETIME(3),
  row_version      INT 默认 1（≥1）
)
```

目标增量约束：`code/key` 与关联记录一致；`UNIQUE(report_record_id)`、
`UNIQUE(idempotency_key)`；`KEY(status, lease_expires_at)`。ORM 已声明于
`app/models/report/report.py`（`REPORT_TASK_TABLE`），**未纳入建表清单**；
部署前执行所有权回退为 `report_record` 行版本栅栏。范围（006）与审计
（043）字段同属待评审增量，不由此文件确定。

## 回滚

- 切换前：停止相关调度/生成写入，保存报告、指标、配置及外部调用记录，
  恢复已验证备份；不回滚已发生的外部通知/CRM 写入。
- 切换后回退：先停写、记录增量再回退；不能因报告只读上游就认为没有自身
  新增业务数据或外部模型副作用。
- 权限收紧虽不改表，仍需与代码/前端同步发布和回退。
- 报告模块 DDL 含 DROP TABLE，不得当作日常升级脚本执行。
