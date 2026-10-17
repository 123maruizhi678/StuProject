/** 各组员仅维护自己的页面；交付后登记入口并将 delivered 改为 true。 */
export const MODULES = [
  { id: "agent", number: "01", name: "客服 Agent", english: "CUSTOMER SERVICE", description: "连接咨询与服务，让每一次沟通更有回应。", pageIds: ["agent"], moduleIds: ["agent_center"], entry: "/static/agent/agent.html", delivered: false, symbol: "◌", accent: "cyan" },
  { id: "customer", number: "02", name: "客户研判", english: "CUSTOMER INSIGHTS", description: "整合客户信息，支持清晰、审慎的业务判断。", pageIds: ["customer_research"], moduleIds: ["customer_research"], entry: "/static/customer/customer.html", delivered: false, symbol: "⌁", accent: "violet" },
  { id: "enterprise", number: "03", name: "企业智能助手", english: "ENTERPRISE ASSISTANT", description: "聚合日常工作，连接团队与企业服务。", pageIds: ["employee_dashboard"], moduleIds: ["employee_workspace"], entry: "/static/enterprise/enterprise.html", delivered: false, symbol: "▦", accent: "blue" },
  { id: "student", number: "04", name: "学生智能助手", english: "STUDENT ASSISTANT", description: "围绕学习与校园事务，提供连贯的服务入口。", pageIds: ["student_dashboard"], moduleIds: ["student_workspace"], entry: "/static/student/student-assistant.html", delivered: false, symbol: "◇", accent: "green" },
  { id: "report", number: "05", name: "智能报告", english: "INTELLIGENT REPORTS", description: "汇聚业务指标，让信息转化为可读的分析。", pageIds: ["report"], moduleIds: ["report_center"], entry: "/static/report/report.html", delivered: false, symbol: "▤", accent: "amber" },
];

export function canAccess(module, access) {
  return module.pageIds.some(id => Object.hasOwn(access?.pages || {}, id)) ||
    module.moduleIds.some(id => Object.hasOwn(access?.modules || {}, id));
}

export function moduleEntry(module) {
  try {
    const url = new URL(module.entry, window.location.origin);
    if (url.origin === window.location.origin && url.pathname.startsWith("/static/") && url.pathname.endsWith(".html")) return url.pathname + url.search + url.hash;
  } catch { /* 只允许本系统已登记的 HTML 页面。 */ }
  return null;
}

export function safeReturnPath(value) {
  try {
    const url = new URL(value || "/", window.location.origin);
    if (url.origin === window.location.origin && ["/", "/account"].includes(url.pathname)) {
      return url.pathname + url.search + url.hash;
    }
  } catch { /* 无效返回地址统一回主入口。 */ }
  return "/";
}
