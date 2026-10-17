# StuProject

后端按技术层分为api、core、schemas、services、repositories、models、clients、tasks，每层再按业务模块分包。

- 统一配置：根目录.env经app/config.py读取；不随模块复制配置。
- 开发启动（项目根目录）：`conda run -n SST python -m uvicorn app.main:app --reload`。
- 前端：frontend/index.html；公共资源位于frontend/js/common和frontend/css/common，资源URL以/static为既有前缀。
- 报告结构预览（不连接数据库）：`conda run -n SST python scripts/report/init_report_tables.py --dry-run`。
- 学生成绩旧DSL导出脚本：scripts/student/export_student_scores.py，输出到dify/student/legacy；不是新增部署应用。
- 当前目录与逐文件迁移记录见业务文档/09杂谈/马睿智/操作文档.md第七章及同目录迁移清单。

尚未交付的enterprise_student旧重复入口及学生请假Dify适配器按已有文档约定暂略，app.main仅装配已交付依赖的原有接口，不注册占位业务。客服原挂载状态不变。目录变更不改数据库、不覆盖真实.env、不启动任务或发布Dify。
