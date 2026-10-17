# 客服 Agent 增量与种子说明

本目录放客服 Agent（六表）的增量脚本与种子数据。建表基线以 `scripts/sql/bk/客服Agent/` 历史脚本与 `all.sql` 为参考；日常变更在本目录登记，执行前先核对目标库实际结构与版本。

## 文件

| 文件 | 作用 |
| --- | --- |
| `agent_schema.sql` | 客服六表独立 DDL（测试/独立库用），含两条客服外键 |
| `agent_seed.sql` | 正式种子数据：7 门课程、4 个活动、8 条 FAQ |
| `agent_test_data.sql` | 少量测试数据（面向空表）：课程 3、活动 2、FAQ 3、会话 2、报名 2（1 有效+1 取消）、消息 4，附逐表查看与对账语句 |

## agent_test_data.sql 使用说明

- 幂等：`course_project` / `lecture_event` / `faq` 的 INSERT 未带唯一业务键，重复执行会产生重复数据；执行前确认库为空，或按需改为 `INSERT IGNORE` / 先清理。
- 活动 `quota` 为 0 表示不限名额；`status` 取值：报名中 / 已满 / 已结束。
- 课程 `status` 取值：上架 / 下架；列表接口只返回上架课程。
- 种子内容为留学机构常见示例，接入前请替换为机构真实数据。

## 判重与锁口径（与 ORM、服务层一致）

- `event_signup` 去重为**状态式**（`status='有效'`），不建 `(event_id, customer_phone)` 永久唯一索引，避免取消后无法重报；
- 历史 `all.sql` 中的 `uk_event_phone` 永久唯一索引与目标规范不一致，启用取消 / 重报前须受控处理索引差异。
