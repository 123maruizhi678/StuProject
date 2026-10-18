export const STUDENT_PAGES=[['overview','学习工作台','grid','/static/student/student-assistant.html','所有服务，一目了然'],['chat','智能助手','spark','/static/student/chat.html','对话咨询 · 确认办理'],['academics','课程与考务','book','/static/student/academics.html','课程 · 成绩 · 学业节点'],['leave','请假服务','calendar','/static/student/leave.html','申请 · 查询 · 撤回'],['tickets','投诉与建议','ticket','/static/student/tickets.html','反馈 · 沟通 · 评价'],['reminders','学业提醒','clock','/static/student/reminders.html','重要节点，不再错过'],['progress','申请进度','route','/static/student/progress.html','文书 · 院校 · 签证'],['care','情绪关怀','heart','/static/student/care.html','倾听感受 · 获得支持'],['notifications','消息中心','bell','/static/student/notifications.html','业务动态 · 站内通知']];

/** 页面交付和业务接口就绪分别登记；入口权限始终来自后端。 */
export const MODULES = [
  { id: "agent", number: "01", name: "客服 Agent", english: "CUSTOMER SERVICE", description: "连接咨询与服务，让每一次沟通更有回应。", pageIds: ["agent"], moduleIds: ["agent_center"], entry: "/static/agent/agent.html", delivered: true, apiReady: true, apiPrefix: "/agent", symbol: "◌", accent: "cyan" },
  { id: "customer", number: "02", name: "客户研判", english: "CUSTOMER INSIGHTS", description: "整合客户信息，支持清晰、审慎的业务判断。", pageIds: ["customer_research"], moduleIds: ["customer_research"], entry: "/static/customer/customer.html", delivered: true, apiReady: true, apiPrefix: "/customer", symbol: "⌁", accent: "violet" },
  { id: "enterprise", number: "03", name: "企业智能助手", english: "ENTERPRISE ASSISTANT", description: "聚合日常工作，连接团队与企业服务。", pageIds: ["employee_dashboard"], moduleIds: ["employee_workspace"], entry: "/static/enterprise/assistant.html", delivered: true, apiReady: true, apiPrefix: "/enterprise", symbol: "▦", accent: "blue" },
  { id: "student", number: "04", name: "学生智能助手", english: "STUDENT ASSISTANT", description: "围绕学习与校园事务，提供连贯的服务入口。", pageIds: ["student_dashboard"], moduleIds: ["student_workspace"], entry: "/static/student/student-assistant.html", delivered: true, apiReady: true, apiPrefix: "/student", symbol: "◇", accent: "green" },
  { id: "report", number: "05", name: "智能报告", english: "INTELLIGENT REPORTS", description: "汇聚业务指标，让信息转化为可读的分析。", pageIds: ["report"], moduleIds: ["report_center"], entry: "/static/report/report.html", delivered: true, apiReady: true, apiPrefix: "/report", symbol: "▤", accent: "amber" },
  { id: "dashboard", number: "06", name: "数据看板", english: "BUSINESS OVERVIEW", description: "查看经营指标、客户趋势与服务进展。", pageIds: ["admin_dashboard"], moduleIds: ["admin_workspace"], entry: "/static/dashboard/dashboard.html", delivered: true, apiReady: false, apiPrefix: "/dashboard", symbol: "◫", accent: "blue" },
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
    if (url.origin === window.location.origin && (["/", "/account", "/student-assistant", ...MODULES.map(item => item.entry), ...STUDENT_PAGES.map(item => item[3])].includes(url.pathname))) {
      return url.pathname + url.search + url.hash;
    }
  } catch { /* 无效返回地址统一回主入口。 */ }
  return "/";
}
