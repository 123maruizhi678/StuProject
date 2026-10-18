# 企业管理模块迁移记录

日期：2026-10-17。来源：`C:\Users\Windows\Desktop\qy`；目标：`D:\project\StuProject`。依据用户指定的 `开发文档/项目目录架构_最终汇总.md`，保留技术分层，每层按业务模块分包。

## 文件归位

本次迁入 120 个源文件；其中 114 个目标原先不存在、4 个与目标一致、2 个前端文件备份后替换。逐文件来源、目标及 SHA-256 见 [migration-manifest.json](migration-manifest.json)。

```text
app/
  api/enterprise/             企业 HTTP 接口
  core/enterprise/            员工权限、SQL 校验
  schemas/enterprise/         请求和响应契约
  services/enterprise/        客户、日报、知识、成绩、工单、教务等服务
  repositories/enterprise/    数据访问与并发控制
  models/enterprise/          跟进、日报、知识、课程和选课
  clients/enterprise/         Dify、NL2SQL、本地 ASR
  tasks/enterprise/           包已归位；任务实现源文件缺失
  api,schemas,services/common/ 配套管理员开户
  core/common/               电话保护、管理员身份、职位映射等共享依赖
  models/common/             复用既有唯一共享映射，加入学业节点和申请进度
  enterprise_policy.yaml
  position_roles.yaml
dify/enterprise/             四个现有工作流和说明
frontend/enterprise/pages/   18 个独立企业业务子页
frontend/js/enterprise/      企业前端脚本
frontend/css/enterprise/     企业样式
frontend/admin/              配套账户管理页面及 js/admin、css/admin 资源
scripts/enterprise/          企业检查、迁移、任务及本地运维脚本
scripts/sql/enterprise/      增量 SQL 与计划
scripts/sql/bk/企业智能助手/  既有历史资料，去重保留
tests/enterprise/            企业、开户及浏览器回归
```

## 合并处理

- 修正迁入 Python 文件的旧导入，统一使用 `app/core/common`、`app/services/common` 等分层路径。
- 在唯一 `app/main.py` 挂载企业和管理员开户路由，保留现有客服、报告及公共入口；企业页面为 `/enterprise`，账户管理为 `/admin/accounts`。
- 保留目标项目的认证、数据库连接及共享表约束。共享映射新增 CRM 学生标识、工单 SLA 快照，复用唯一 `Base.metadata`；数据库变更说明见 `scripts/sql/enterprise/README.md`。
- 企业配置合入 `app/config.py`，沿用根目录唯一 `.env`。没有修改真实 `.env`，没有启用源项目的第二份本地配置。
- 企业和账户页面接入公共会话，保留源页面既有登录入口；主工作台的企业模块登记同步更新。
- 当前项目共享代码、源目录中其他模块和公共入口保留。没有读取或修改其他业务文档、开发文档。

## 备份与校验

- 备份目录：`.migration_backups/enterprise_20261017/`。
- `incoming/` 保存全部 120 个源文件原始快照；`previous/` 保存覆盖或合并前的目标文件。
- 来源清理仅针对清单中的 120 个文件，并先校验来源、原始快照、最终目标的哈希。Python 导入修正等会改变目标哈希，清单同时保留原始及最终哈希。
- 原始配置、其他业务文件、日志和缓存没有作为企业模块整体搬入。

## 验证结果与现有限制

- 公共 Python 回归：39/39；客服：18/18；智能报告：38/38；前端静态与请求回归：14/14。
- 企业 Python 回归：39/42 通过，3 项因源目录未提供 `app/tasks/enterprise/enterprise_tasks.py` 报错。未编造通知任务实现；`run_enterprise_tasks.py` 会明确提示缺失文件。
- 69 个迁入 Python 文件通过语法解析；企业及共享依赖导入成功；75 个企业接口操作标识无重复；企业页面、账户页面、样式和脚本可访问；未登录请求被拒绝。
- 未执行真实数据库迁移、Dify 工作流发布、本地模型下载或演示数据初始化；浏览器脚本已迁入，尚未执行。

目录迁移完成不代表缺失任务、数据库增量和外部服务已经交付或联调通过。
