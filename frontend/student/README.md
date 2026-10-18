# 学生工作台增量接入

本次基于 main 统一登录与工作台，保留其他模块的页面、权限和数据映射。

## 入口与功能

- 使用统一登录页 `/login.html`，学生入口 `/student/student-assistant.html`。
- `js/workspace/live.js` 仅在学生页面加载 `js/student/workspace-enhancements.js`。学生导航与操作按本人身份、动作权限筛选；服务端仍逐请求核验对象范围。
- 学生姓名从 `GET /api/v1/student/profile` 读取，只返回本人 student_id、student_no、full_name；没有修改公共认证接口。
- 顶部未读数量每30秒查询，页面隐藏时暂停；标记已读后立即刷新。凭据变化、退出或页面卸载后停止。
- 聊天页从 `GET /api/v1/student/chat/sessions` 与 `GET /api/v1/student/chat/sessions/{session_id}` 恢复本人历史，支持 limit、offset 分页。浏览器仅按账号记录当前会话编号，不保存正文。
- 恢复会话使用当前版本重新签发的会话凭证；旧办理预览只读，不恢复提交按钮。执行中或待核实的模型轮次会阻止继续发送，刷新仅查询，不重发模型请求。
- 无新增数据库结构，复用已有会话与轮次表。需同时部署学生接口和前端，并沿用现有 JWT、学生签名密钥和 Dify 配置。

## 验证

- 后端：`python -m pytest tests -q`（可按主项目说明使用 `.runtime/backend-deps`）。
- 公共前端：`node --test tests/common/test_frontend.mjs`。
- 学生交互：安装 jsdom 到临时工具目录，将其 node_modules 设为 NODE_PATH 后执行 `node --experimental-vm-modules --test tests/student/workspace-enhancements.test.mjs`。测试使用虚构接口与 DOM，不会访问真实数据库或 Dify。

Git 更新不代表局域网服务器自动部署。服务器需拉取相同提交并重新加载前后端；可通过 OpenAPI 中的 `/api/v1/student/profile` 和 `/api/v1/student/chat/sessions` 判断学生新增接口是否已部署。
