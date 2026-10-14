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
mysql -uroot -p12345 education_agent < scripts/report_module_ddl.sql
```

与 ORM 建表的关系：

- `app/models/report.py` 提供相同的三张表 ORM 模型，执行 `init_db.py` 也会一并创建；
- `report_module_ddl.sql` 便于脱离应用环境独立初始化，两者表结构保持一致；
- 脚本末尾附录给出报告依赖的上游表（`intention_customer`、投诉工单、跟进记录）的字段补充建议，供对应模块建表时参考，报告模块不重复建表。
