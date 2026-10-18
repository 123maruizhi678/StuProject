# 留学项目平台前端

保留学院风布局，69 个主要页面和 5 个兼容入口现通过真实 API 使用本地 MySQL 业务数据。

在项目根目录运行 `npm run dev`，启动后自动打开 `http://192.168.5.12/login.html`，同一局域网设备可使用该地址访问，无需填写端口或配置域名解析。Vite 监听 HTTP 80 端口，本机也可通过 `http://127.0.0.1/login.html` 访问。账号 `root`、密码 `root`。首次使用局域网访问时，在管理员 PowerShell 中运行根目录的 `scripts/setup-lan.ps1` 配置防火墙。

Vite 配置位于根目录 `vite.config.mjs`，将 `/api`、`/health`、`/openapi.json` 代理到 `127.0.0.1:8000`。`/static/*` 和旧登录/工作台地址兼容原有入口。直接双击 HTML 不能使用业务接口。

业务页面使用 `js/workspace/pages.js` 的资源登记与 `js/workspace/live.js` 的共享表单、表格及响应处理。字段约束来自后端契约；账号管理契约仅在管理员登录后读取。登录令牌只保存在当前标签页；退出时同步清除业务记录选择和确认预览。

读取列表后选择记录，可以回填编号和当前版本；提交失败时保持相同请求的幂等键。提醒更新时间按原始微秒精度回传。上传使用 FormData，支持当前契约中的 contentMediaType 文件描述。模型预览与业务确认分开提交。

没有配置的模型、同步和语音能力显示实际不可用原因；不会返回模拟成功。学生本人业务需要学生身份，管理员可通过账号管理创建。

- `npm run test:frontend`：公共请求、会话、权限、上传、幂等和时区单元测试。
- `npm run test:system`：Edge 浏览器遍历全部页面，并通过 Vite 连接真实后端执行业务表单。先运行后端验收脚本准备带 QA 标识的业务身份。
- 浏览器测试脚本：`scripts/testing/browser-system.mjs`；测试结果及截图写入 `.runtime`。

页面总览为 `common/sitemap.html`；完整系统启动与外部服务后续方案见根目录 README。
