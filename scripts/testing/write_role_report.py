"""Create a reviewable account and scenario report from recorded evidence."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
directory = ROOT / '.runtime/role-simulation'
run = json.loads((directory / 'run.json').read_text(encoding='utf-8'))
db = json.loads((directory / 'database-verification.json').read_text(encoding='utf-8'))
refresh = json.loads((directory / 'ui-refresh.json').read_text(encoding='utf-8'))
ids, summary = run['ids'], run['summary']
labels = {
    'manager': 'A 部主管', 'consultant': 'A 部招生顾问', 'teacher': 'A 部班主任',
    'academic': 'A 部教务', 'counselor': 'A 部学生关怀老师', 'employee': 'A 部普通员工',
    'consultantB': 'B 部招生顾问', 'teacherB': 'B 部班主任', 'customer': 'A 部客户',
    'student': 'A 部学生甲', 'studentB': 'B 部学生乙',
}
flows = [
    '管理员登录并创建两个独立部门', '管理员创建八个员工账号并配置职位',
    '管理员创建一个客户及两名学生，关联客户与学生', '全部角色独立登录并进入对应工作台',
    '管理员创建课程，绑定班主任、关怀老师及成绩维护教务',
    '顾问首次联系客户，记录电话跟进，将意向更新为 qualified',
    '主管查看部门客户并分派顾问；B 部顾问读取 A 部客户被拒绝',
    '教务给学生选课，录入成绩 86，复核更正为 91',
    '学生与本班班主任读取真实课程成绩；其他学生及班主任无法读取',
    '教务安排考试，学生设置提前一天提醒；考试改期后提醒自动重排',
    '顾问维护申请进度，学生看到文书审核已完成',
    '学生请假，本班主班主任审批同意，学生查询结果',
    '学生提交另一份请假后撤回',
    '学生发起工单，主管分派班主任，班主任公开答复',
    '学生补充反馈，班主任提交处理方案',
    '学生对方案提出补充要求并重开工单，班主任补充方案',
    '学生确认问题解决并给出 5 分评价',
    '普通员工提交日报，主管读取本部门日报，跨部门日报访问被拒绝',
    '管理员发布部门知识，部门员工可读，B 部员工访问被拒绝',
    '运行实际通知任务，学生读取已投递通知并标记已读',
    '跨学生请假及工单隔离；跨班主任请假隔离；非教务改成绩被拒绝；普通身份无开户入口',
    '客户查看个人账号与公开课程、活动',
    '关怀老师可查看授权预警列表，普通班主任访问被拒绝',
    '管理员从前端查看操作审计',
    'AI 对话、真实心理评估及基于新评估的人工预警闭环',
    '报告收单、回执和状态查询；AI 正文生成',
    '全程无浏览器脚本运行错误',
]
lines = [
    '# 前端多角色业务运行模拟报告', '',
    f'本轮编号：`{run["run_id"]}`。浏览器执行：{run["started_at"]} 至 {run["finished_at"]}（UTC）。', '',
    f'从真实前端以 `root/root` 开始创建 {summary["accounts"]} 个账号，完成 {summary["scenarios"]} 组场景：'
    f'{summary["passed"]} 组通过，{summary["skipped"]} 组因外部服务缺失跳过，{summary["failed"]} 组失败。'
    f'另补测同一记录连续修改，结果 {refresh["status"]}。MySQL 只读核验 {db["summary"]["passed"]} 项通过，{db["summary"]["failed"]} 项失败。', '',
    '业务创建、查询、修改和审批都通过 Edge 中的真实页面表单执行，经 Vite 代理访问后端。没有用脚本直写数据库或替换业务依赖。'
    '通知投递通过项目实际任务脚本触发。数据库核对采用 `START TRANSACTION READ ONLY`。', '',
    '## 登录及账号', '',
    '- 前端入口：http://127.0.0.1:5173/common/login.html',
    '- 管理员：`root`，密码 `root`。',
    '- 本轮新账号初始密码统一为 `123456`；数据库保存 Argon2 哈希。',
    f'- A 部：`{ids["departmentA"]}`；B 部：`{ids["departmentB"]}`。部门名称包含本轮编号。', '',
    '| 身份 | 用户名 | 用户编号 | 部门编号 |', '| --- | --- | ---: | ---: |',
]
for role, account in run['accounts'].items():
    lines.append(f'| {labels[role]} | `{account["username"]}` | {account["user_id"]} | {account["department_id"]} |')
lines += ['', '账号完整清单：[accounts.csv](../../.runtime/role-simulation/accounts.csv)。全部账号及业务记录保留在实际业务表中，未回滚。', '',
          '## 场景结果', '', '| 序号 | 业务场景 | 结果 |', '| ---: | --- | --- |']
for index, scenario in enumerate(run['scenarios'], 1):
    result = {'passed': '通过', 'failed': '失败', 'skipped': '跳过'}[scenario['status']]
    lines.append(f'| {index} | {flows[index-1]} | {result} |')
lines += ['', '## 最终业务状态及证据', '',
          '| 业务记录 | 编号 | 最终状态 |', '| --- | ---: | --- |',
          f'| 客户 | {ids["customer"]} | qualified，顾问负责，版本 5 |',
          f'| 学生甲 / 学生乙 | {ids["student"]} / {ids["studentB"]} | 两个独立部门，客户关联正确 |',
          f'| 课程 / 选课 | {ids["course"]} / {ids["enrollment"]} | active，2026-FALL |',
          f'| 学生成绩 | {ids["score"]} | 91/100，valid，版本 2，教务录入及更正 |',
          f'| 考试 / 提醒 | {ids["event"]} / {ids["reminder"]} | 事件版本 2，提醒版本同步为 2，提前 1440 分钟 |',
          f'| 申请进度 | {ids["progress"]} | document_review / completed，版本 2 |',
          f'| 请假 / 撤回请假 | {ids["leave"]} / {ids["withdrawnLeave"]} | approved / cancelled，版本均为 2 |',
          f'| 工单 | {ids["ticket"]} | closed，重开 1 次，5 分，版本 9 |',
          f'| A 部日报 / B 部日报 | {ids["daily"]} / {ids["dailyB"]} | submitted；A 部日报补测后版本 {refresh["final_version"]} |',
          f'| 部门知识 | {ids["knowledge"]} | published，index_status=ready，A 部范围 |',
          f'| 学生通知 | {ids["notification"]} | sent，read_at 已记录 |', '',
          f'业务模拟显式观测 {summary["ui_requests"]} 次页面请求；连续修改补测另增加 {len(refresh["calls"])} 次写入。'
          f'共 {db["snapshot"]["audit_counts"]["successful_ui_writes"]} 次成功业务写入与成功操作审计逐条匹配，员工和学生操作者一致。'
          '报告收单使用独立报告记录，不纳入该业务审计计数。', '',
          '预期拒绝属于测试通过：跨部门/跨学生记录返回 404；无对应岗位权限的改成绩与预警查询返回 403。', '',
          '## 本轮修复及回归', '',
          '发现页面保存后列表保留旧版本，重新选择同一记录会把旧版本带回表单，存在下一次提交发生版本冲突的风险。'
          '已在 `frontend/js/workspace/live.js` 中增加成功写入后刷新本页已读取列表的处理，保留当前筛选条件。', '',
          '通过员工真实日报连续两次修改验证：版本从 1 到 2 再到 3；每次列表自动刷新，重新选择后使用最新版本，页面无需重新加载。'
          '补测无浏览器运行错误。14 项现有前端测试通过，JavaScript 语法检查通过。只读核验脚本首次误用了员工启用字段，已按实际 `status` 字段修正；这不是系统业务故障。', '',
          '## 外部服务限制', '',
          '- 未配置真实 AI 服务，AI 对话和心理评估未执行；没有编造风险评估或生成预警，因此本轮新增预警的接手、跟进、关闭流程未完成。已验证关怀老师的授权入口和普通班主任拒绝访问。',
          f'- 报告记录 `{ids["report"]}` 的页面收单与状态读取成功，最终状态 `{run["report_state"]}`；未把回执成功计为正文生成成功。',
          '- 外部系统同步、语音及其他未配置服务仍按原范围跳过，接入方案见 [EXTERNAL_SERVICES_PLAN.md](EXTERNAL_SERVICES_PLAN.md)。', '',
          '## 可复查文件', '',
          '- [前端场景及请求记录](../../.runtime/role-simulation/run.json)',
          '- [MySQL 只读核验结果](../../.runtime/role-simulation/database-verification.json)',
          '- [连续修改回归结果](../../.runtime/role-simulation/ui-refresh.json)',
          '- [账号创建截图](../../.runtime/role-simulation/admin-created-accounts.png)',
          '- [学生实际成绩页面](../../.runtime/role-simulation/student-real-academics.png)',
          '- [学生工单确认与评价页面](../../.runtime/role-simulation/student-closed-ticket.png)',
          '- [学生通知页面](../../.runtime/role-simulation/student-notifications.png)',
          '- [连续修改后的日报页面](../../.runtime/role-simulation/employee-daily-after-consecutive-edits.png)', '',
          '重跑说明：`node scripts/testing/role_simulation.mjs --resume` 复用本轮已完成数据；去掉 `--resume` 会创建新一轮账号和业务记录。'
          '`node scripts/testing/role_ui_refresh.mjs` 在当前日报版本上再次执行两次真实页面修改；随后运行 `verify_role_simulation.py` 和本脚本更新报告。', '']
target = ROOT / 'scripts/testing/ROLE_SIMULATION_REPORT.md'
target.write_text('\n'.join(lines), encoding='utf-8')
print(str(target))
