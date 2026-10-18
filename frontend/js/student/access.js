// 入口和按钮可见性；实际授权始终由服务端执行。
export const studentPermissions={overview:['dashboard.student'],chat:['student.chat'],academics:['student.course.read_own','student.score.read_own','student.academic.read_own'],leave:['student.admin_service.read_own'],tickets:['service_ticket.read_own'],reminders:['student.reminder.manage_own'],progress:['student.progress.read_own'],care:['student.mental.create_own'],notifications:['student.notification.read_own']};
let access=null;
export const setAccess=value=>{access=value;};
export const getAccess=()=>access;
export const can=permission=>!!access?.permissions?.includes(permission);
export const allowedPage=(kind,page)=>access?.identity_type===kind&&studentPermissions[page]?.some(can);
export function applyPermissions(root=document){root.querySelectorAll('[data-permission]').forEach(el=>{const allowed=el.dataset.permission.split(' ').some(can);el.hidden=!allowed;el.classList.toggle('hidden',!allowed);if('disabled' in el&&!allowed)el.disabled=true;});}
