# StuProject · 公共登录与权限入口

本目录仅保留公共基础能力的代码和运行配置。实现依据为开发文档中的《操作文档.md》和《项目目录架构_最终汇总.md》。

提供账号登录、公开访问清单、本人权限清单，以及 JWT、逐接口权限依赖、数据库会话、统一响应、日志和通用 Dify HTTP 工具。业务模块的精确权限映射保留在公共策略中，具体业务代码和应用配置已移除。

## 启动

在项目根目录执行：

```powershell
conda activate SST
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

打开 [登录页面](http://127.0.0.1:8000/login) 或 [接口文档](http://127.0.0.1:8000/docs)。

本机 .env 已保留既有数据库连接，并配置随机 JWT 密钥；不要提交此文件。新环境参考 .env.example，依赖使用 environment.yml。

## 首次开通账号

数据库表已存在时不要重跑初始化建表文件。检查公共结构后，交互设置第一个平台管理员的密码：

```powershell
python scripts/common/check_shared_schema.py
python scripts/common/create_account.py --username admin --bootstrap-admin
```

首次开通仅适用于没有任何账号的数据库。脚本不会创建默认密码或公开注册接口。密码至少8位，交互输入，不在命令行、日志或文档中保存。

后续账号由现有平台管理员开通；员工、客户和学生必须先有真实主档。例如：

```powershell
python scripts/common/create_account.py --username employee001 --identity employee --business-id 1 --operator admin
```

脚本只关联已有主档，不代建员工/学生、分配业务角色或修改关系。

## 验证

```powershell
python -m unittest discover -s tests -t . -v
python scripts/common/check_shared_schema.py
```

测试使用隔离的内存数据库，不依赖真实 Dify。完整目录见《项目目录架构_最终汇总.md》，权限边界、数据库增量与接口示例见《操作文档.md》及 app/README.md。

按用户要求，所有后续操作跳过业务文档文件夹。已有36张数据库表和开发文档保留。
