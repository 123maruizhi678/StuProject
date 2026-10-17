"""添加学生精确权限，不覆盖其他模块策略；开发时执行一次。"""
from pathlib import Path
import yaml
p=Path(__file__).resolve().parents[2]/'app/access_control.yaml'
data=yaml.safe_load(p.read_text(encoding='utf-8'))
student=["student.admin_service.create","student.admin_service.read_own","student.admin_service.withdraw_own","service_ticket.create","service_ticket.read_own","student.ticket.reply_own","student.ticket.confirm_own","student.ticket.rate_own","student.mental.create_own","student.course.read_own","student.score.read_own","student.academic.read_own","student.progress.read_own","student.reminder.manage_own","student.reminder.manage_own","student.notification.read_own","student.notification.read_own","student.chat","student.action.confirm","course_project.read"]
current=data['roles']['student']['permissions']
data['roles']['student']['permissions']=list(dict.fromkeys(current+student))


roles=data.setdefault('employee_roles',{})
packages={'teacher':['student.admin_service.review','student.notification.read','student.notification.read','student.warning.read','student.warning.handle','student.warning.handle'], 'manager':['student.admin_service.assign','student.progress.maintain','report.read'], 'academic':['student.academic.maintain'], 'consultant':['student.progress.maintain']}
for role,perms in packages.items():
    entry=roles.setdefault(role, {'permissions':[]})
    entry['permissions']=list(dict.fromkeys(entry.get('permissions',[])+perms))
data['pages']['student_assistant']={'title':'学生助手','route':'/student-assistant','requires_auth':True,'permission':'student.chat'}
module=data['modules'].setdefault('student', {'title':'学生助手','required_any':['dashboard.student']})
module['pages']=list(dict.fromkeys(module.get('pages',[])+['student_assistant']))
p.write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=False),encoding='utf-8')
