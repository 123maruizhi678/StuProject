# 前端素材

公共工作台与学生页面使用本地 HTML、CSS、JavaScript 和 SVG/CSS 图形，不依赖外部字体、图片或视频。业务新增素材请按模块置于 `assets/<module>/`，避免覆盖公共资源。

下载版本的可选背景视频槽保留于 `js/common/effects.js`：页面加入 `id="bgVideo"` 的静音循环 `<video>` 后，会依次探测 `/static/assets/bg.mp4`、`/static/assets/bg.webm`。当前没有附带或下载视频，也没有在默认页面启用该探测；背景使用本地 Canvas 粒子和 CSS 极光。动效遵循 `prefers-reduced-motion`。
