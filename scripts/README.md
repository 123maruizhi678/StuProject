# 建表脚本与说明

本目录存放数据库初始化相关脚本与文档。

## 目录结构

```
scripts/
├── init_db.py             # 建表脚本：根据 ORM 模型创建所有表
├── report_module_ddl.sql  # 智能报告模块建表脚本（纯 SQL，可直接执行）
└── README.md              # 本说明文档
```

## 前置条件

1. 本机已安装并运行 **MySQL**，且 `.env` 中的数据库连接参数正确：
   - `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME`
2. 已激活 Conda 环境 `SST`（已包含 `pymysql`、`sqlalchemy`）。
3. 在 `app/models/` 下定义好 ORM 模型（模型模块会被脚本自动导入）。

## 使用方法

在项目根目录 `D:\AI\StuProject` 下执行：

```bash
D:\anaconda3\envs\SST\python.exe scripts/init_db.py
```

脚本会：

- 复用 `app/database.py` 中的 `engine` 与 `Base`；
- 自动导入 `app/models/` 下的所有模型模块；
- 对库中**不存在的表**执行 `CREATE TABLE`；
- 打印建表结果（表数量与表名）。

## 注意事项

- **只建不存在的表**：若表已存在，不会删除或改动其结构。
- **结构变更**：当模型字段/表结构发生变化时，需使用迁移工具（如 Alembic）或手动改表，本脚本不负责增量迁移。
- **与运行时解耦**：应用代码（`app/database.py`）已移除自动建表逻辑，建表完全由此脚本负责，避免在启动时误操作数据库。
- 连接串使用 `mysql+pymysql://...?charset=utf8mb4`。

## 智能报告模块建表脚本

`report_module_ddl.sql` 提供智能报告模块三张核心表（`report_config` / `report_record` / `report_metric`）的纯 SQL 建表脚本，可直接在 MySQL 中执行：

```bash
mysql -uroot -p12345 < scripts/report_module_ddl.sql
```

- **要求 MySQL 8.0.16+**（脚本使用 CHECK 约束，5.7 会报错），建议 8.0 / 8.4。
- 脚本已对齐项目统一规范：`DATETIME(3)` + UTC、`utf8mb4_0900_ai_ci`、编码键 `utf8mb4_bin`、CHECK 约束、真实外键、乐观锁 `row_version`。
- 首次初始化使用：目标库内这三张表应尚不存在；脚本不删除已有表、不插业务数据。

与 ORM 建表的关系：

- `app/models/report.py` 提供相同的三张表 ORM 模型，执行 `init_db.py` 也会一并创建，两者表结构保持一致；
- `report_module_ddl.sql` 便于脱离应用环境独立初始化。

报告依赖的上游表（`customer_profile` / `customer_followup` / `employee_daily_report` / `mental_health_profile` / `mental_warning` / `service_ticket`）由企业、学生模块建表，报告模块只读聚合，不在本脚本重复建表。投诉工单的事实源目前存在 `service_ticket`（企业）与 `after_sales_ticket`（学生草案）两套命名，需在两端统一后确定，脚本附录已标注。
