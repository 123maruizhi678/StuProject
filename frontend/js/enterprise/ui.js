import {labels, enums} from './catalog.js';
export function display(key, value) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? '是' : '否';
  if (enums[key]?.[value]) return enums[key][value];
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  if (/_at$|valid_from$|valid_to$|effective_from$/.test(key) && typeof value === 'string') {
    const date = new Date(/Z$|[+-]\d\d:\d\d$/.test(value) ? value : value+'Z');
    if (!Number.isNaN(date.getTime())) return date.toLocaleString('zh-CN', {timeZone:'Asia/Shanghai',hour12:false});
  }
  return String(value);
}
export const fieldLabel = key => labels[key] || key;
export const pageMeta = {
  todos:['工作中心','聚焦当前账户需要推进的事项。'],
  customer:['客户协作','管理客户档案、跟进记录与服务进度。'],
  'daily-report':['团队协作','记录每天的工作进展，让沟通有迹可循。'],
  students:['教务管理','查看授权范围内的学生档案。'],
  scores:['教务管理','维护课程考核与学生成绩。'],
  courses:['教务管理','维护课程目录与课程状态。'],
  'student-courses':['教务管理','管理学生、课程与学期之间的选课关系。'],
  'academic-events':['教务管理','跟进考试安排和重要截止日期。'],
  'application-progress':['客户协作','推进文书、院校申请和签证办理。'],
  tickets:['客户协作','分派服务工单，记录回应与解决方案。'],
  knowledge:['团队协作','沉淀制度、标准问答与业务经验。'],
  notifications:['工作中心','查阅业务提醒与工作通知。'],
  employees:['组织管理','查看团队成员，维护员工档案。'],
  departments:['组织管理','维护部门结构与职能信息。'],
  'student-bindings':['组织管理','配置学生负责人及课程授权关系。'],
  'operation-logs':['组织管理','查看授权范围内的业务操作记录。']
};
