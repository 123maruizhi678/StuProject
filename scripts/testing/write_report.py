"""Build the reviewable acceptance report from recorded test evidence."""
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
runtime=ROOT/'.runtime'


def main():
    backend=json.loads((runtime/'backend-system.json').read_text(encoding='utf-8'))
    supplement=json.loads((runtime/'backend-supplement.json').read_text(encoding='utf-8'))
    browser=json.loads((runtime/'browser-system.json').read_text(encoding='utf-8'))
    rows=[]
    for operation in backend['operations']:
        regex='^'+re.sub(r'\{[^}]+\}',r'[^/]+',operation['path'])+'$'
        extra=[c for c in supplement['calls'] if c['method']==operation['method'] and re.match(regex,c['path'])]
        codes=sorted(set(operation['codes']+[c['code'] for c in extra]))
        rows.append({'method':operation['method'],'path':operation['path'],
            'requests':operation['requests']+len(extra),'success_response':0 in codes,'codes':','.join(map(str,codes))})
    with (runtime/'interface-coverage.csv').open('w',encoding='utf-8-sig',newline='') as out:
        writer=csv.DictWriter(out,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    missing=[row for row in rows if not row['success_response']]
    primary=re.search(r'(\d+) passed, (\d+) subtests passed',(runtime/'all-tests.log').read_text(encoding='utf-8'))
    node=re.search(r'pass (\d+)',(runtime/'frontend-unit.log').read_text(encoding='utf-8'))
    summary=backend['summary'];web=browser['summary'];sup=supplement['summary']
    limits='\n'.join(f"| {row['method']} `{row['path']}` | {row['codes']} |" for row in missing)
    report=f'''# 本地全系统验收报告

验收时间：{datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M')}（北京时间）。

## 当前运行状态

- 完整启动命令：项目根目录执行 `npm run dev` 或 `npm start`。
- 前端：<http://127.0.0.1:5173/common/login.html>；后端：<http://127.0.0.1:8000>。
- 管理员：`root / root`，数据库仅保存 Argon2 哈希。
- Vite 代理 `/api`、`/health`、`/openapi.json` 到本机 8000；启动后自动打开登录页。
- 统一启动包含后端、学生通知任务、企业通知任务、Vite。已从完全停止状态验证启动和停止脚本。
- 本次按照未配置外部服务的约束运行，启动器不发送实际模型请求。

## 验收结果

| 类别 | 结果 | 证据 |
| --- | --- | --- |
| Python 逻辑、权限、事务、模型契约及任务回归 | {primary.group(1)} 项通过，另有 {primary.group(2)} 个子用例通过 | `.runtime/all-tests.log`、`all-tests.xml` |
| 公共前端请求、会话、上传、幂等与时区 | {node.group(1)} 项通过 | `.runtime/frontend-unit.log` |
| 真实 HTTP + MySQL，经 Vite 代理 | {summary['passed']}/{summary['scenarios']} 组通过，{summary['requests']} 次请求 | `.runtime/backend-system.json` |
| 真实 MySQL 协作补测，外层事务整体回滚 | {sup['passed']}/{sup['scenarios']} 组通过，{sup['requests']} 次请求 | `.runtime/backend-supplement.json` |
| Edge 浏览器 | {web['passed']}/{web['checks']} 项通过，{browser['pages']} 页，其中主页面 {browser['primary_pages']} 页、兼容入口 {browser['compatibility_pages']} 页 | `.runtime/browser-system.json` |
| 已注册接口操作覆盖 | {len(rows)}/{len(rows)} 个已遍历；{len(rows)-len(missing)} 个观察到 code=0，{len(missing)} 个验证依赖/参数/权限分支 | `.runtime/interface-coverage.csv` |
| 学生真实表结构核验 | compatible=true，无缺表/缺列 | `.runtime/student-schema-check.json` |
| 真实通知任务单轮 | 学生发送成功、无发送失败；企业领取发布检查通过 | `.runtime/student-worker-check.log`、`enterprise-worker-check.log` |

接口 code=0 表示该操作成功响应；报告生成的 code=0 只表示已受理或回执复用，不能解释为真实模型已经生成正文。
浏览器测试遍历所有页面和操作面板，并实际提交开户、客户增改、课程选课、成绩、学业节点、申请进度、日报、知识发布、文件上传解析研判、请假撤销、工单、提醒撤销、报告配置/生成和公开活动报名。
异常和权限覆盖与成功业务覆盖分别记录，没有将 403/503 当作业务成功。

## 已完成修复

1. 学生和客户研判接口未挂载：装配完整聚合路由，移除失效旧请假入口。
2. 学生/企业重复声明同名学业表导致启动失败：统一共享元数据与 ORM 表映射，补齐外键和微秒时间类型。
3. 缺失运行配置字段及角色策略：补齐学生本地查询、同步、通知、签名、上传目录等配置，以及受控职位映射。
4. 真实库缺少增量字段和课程选课表：已增量补齐，保留原表和记录；空报告配置已初始化五类种子。
5. 报告 MySQL 时间戳使 SQLite 回归全部失败：按数据库方言编译默认值，报告 38 项回归通过。
6. 学生查课读取独立文件，与企业维护的选课不一致：改为读取实际课程/选课表并限定本人有效记录。
7. 前端只有演示登录、示例数据和模拟保存：改为真实认证、真实查询与写入，按身份进入对应工作台。
8. 企业动态路由没有描述路径参数：前端补充必需编号字段，记录选择回填当前编号和版本。
9. 上传契约使用 contentMediaType，原表单未携带文件：修正文件控件识别及 FormData 提交。
10. 提醒更新时间丢失微秒、不同业务间误用版本：保留服务器原始时间戳，限定同一资源回填版本。
11. 未配置学生模型仍写入结果未知占位：在聊天/评估入口提前检查配置；既有签名确认独立办理。
12. 会话退出后业务选择和预览残留：清除本标签页选择/预览，失效时返回登录页。
13. Vite 代理、单入口启停、浏览器自动打开、通知任务启停已接入；桌面和手机布局已检查。

## 未完成实际外部依赖验收的操作

| 操作 | 本次观察业务码 |
| --- | --- |
{limits}

这些操作均已验证可达及明确失败处理。真实模型、音频识别效果和外部拉取成功链路未配置，按用户要求保留方案后跳过。
另外，五类报告的真实模型正文生成也列为待接入；收单、真实取数、失败状态、配置和回执已经测试。
学生心理样本、确认凭证及外部同步批次在补测中明确使用合成输入，只用于验证真实表与后端处理逻辑，没有冒充外部模型输出。
邮件、短信、支付及自助重置密码没有配置或完整适配器；账号协助页明确联系管理员。
详细接入步骤见 [EXTERNAL_SERVICES_PLAN.md](EXTERNAL_SERVICES_PLAN.md)。历史 enterprise_student 空模块未交付，不计入通过功能。

## 数据与改动范围

- MySQL：本机 `education_agent`；没有使用 SQLite 替代真实接口验收。
- root 管理员持久保留。HTTP/浏览器验收资料以 QA、WEB、browser、验收等标识保留，便于继续页面联调。
- 本轮业务身份前缀：`{backend['run_id']}`。这些身份由 root 注册，使用项目开户默认初始密码；学生自助与员工处理分别使用对应身份。
- 补测角色、合成心理评估与同步写入位于外层事务，结束已回滚并检查无新增审计/员工残留。
- 本地密钥只写入原 `.env`，未写入报告；原库结构备份见 `.runtime/backend-schema-before.json`。
- 保留开始时已有的企业任务和测试修改。业务文档、开发文档目录没有搜索、读取或修改。

## 重现

```powershell
npm run dev
# 另开终端，使用 SST Python。若依赖位于本次项目目录：
$env:PYTHONPATH = "$PWD/.runtime/backend-deps"
python -m pytest tests -q
npm run test:frontend
python scripts/testing/backend_system.py --base-url http://127.0.0.1:5173
python scripts/testing/backend_supplement.py
npm run test:system
python scripts/testing/write_report.py
```

后台运行的服务可用 `powershell -File scripts/stop.ps1` 停止。
外部模型和报告任务持久化限制见后续方案；本报告不声称已经完成未配置系统的真实供应商验收。
'''
    (ROOT/'scripts/testing/SYSTEM_TEST_REPORT.md').write_text(report,encoding='utf-8')
    print(json.dumps({'registered_operations':len(rows),'success_responses':len(rows)-len(missing),'dependency_limited_operations':len(missing),'browser_checks':web},ensure_ascii=False))


if __name__=='__main__':main()
