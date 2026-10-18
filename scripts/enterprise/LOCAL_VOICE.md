# 本地语音输入

前端使用浏览器麦克风录音，通过 Vite 将转写接口单独代理到本机
`127.0.0.1:8011`。其余业务接口继续使用 `STUPROJECT_BACKEND_URL`，默认
`http://192.168.5.12:8000`。

首次准备（在项目根目录，使用项目 Python 环境）：

```text
python -m pip install --target .runtime/asr-deps --only-binary=:all: -r scripts/enterprise/requirements-voice.txt
python scripts/enterprise/prepare_local_voice.py
npm run dev
```

准备脚本从 Systran 官方 Hugging Face 仓库下载 base 模型，固定一次下载的
revision，并验证模型文件的 SHA256。来源记录保存在模型目录的 `source.json`。
模型及依赖位于 `.runtime`，不改动 `.env`。运行时不需要访问模型下载网站。

`scripts/dev.mjs` 检测到模型后会一并启动本地语音服务并管理其进程。
可通过进程环境变量 `ASR_MODEL_PATH` 指定其他已准备好的 faster-whisper 模型。
`/local-voice-health` 返回本地服务和模型文件就绪状态。

请通过 `http://localhost:5173/enterprise/assistant.html` 登录使用麦克风；局域网
HTTP 地址需要改为 HTTPS 才能获得浏览器麦克风能力。

每次转写均携带当前登录令牌，向业务后端的 `/api/v1/enterprise/me/permissions`
实时核实 `enterprise.command` 权限。后端离线、会话失效或无权限时拒绝转写。
本地服务仅监听回环地址，不提供业务数据写入接口。录音最多20MiB、5分钟，
前端每次录音最多60秒；录音临时文件在完成或失败后删除。

识别结果统一简体中文，填入原有输入框后由用户核对发送，不自动执行工作指令。
首次模型加载可能比后续识别耗时更长。
