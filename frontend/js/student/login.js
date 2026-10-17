import { safeReturnPath } from "../common/modules.js";

// 旧学生登录地址保留为兼容入口，账号验证统一由公共登录页负责。
const next = safeReturnPath(new URLSearchParams(location.search).get("next") || "/static/student/student-assistant.html");
window.top.location.replace(`/login?next=${encodeURIComponent(next)}`);
