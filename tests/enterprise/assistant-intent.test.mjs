import {test} from 'node:test';
import assert from 'node:assert/strict';
import {inferEnterpriseIntent} from '../../frontend/js/enterprise/assistant-intent.js';
import {visibleModules,pagePath,loginDestination} from '../../frontend/js/common/navigation-model.js';

test('业务请求自动区分操作预览 数据查询和流程咨询',()=>{
  const examples={knowledge:['怎么请假','如何新增客户','删除客户需要什么权限','请假流程是什么','查询客户需要哪些权限'],command:['新增客户张三，意向英国','把王五的客户状态改为已签约','提交今天日报：完成三次回访','查询张三档案并更新状态','帮我写一份日报'],query:['查询本周工作日报','今天新增了多少客户？','统计最近工单数量','所有待签约客户','有哪些课程']};
  for(const [intent,values]of Object.entries(examples))for(const text of values)assert.equal(inferEnterpriseIntent(text),intent,text);
  assert.equal(inferEnterpriseIntent(''),null);assert.equal(inferEnterpriseIntent('姓名张三，部门教务'),null);
});
test('旧企业工作台入口统一到助手且不继续出现在服务端菜单',()=>{
  globalThis.window={location:{origin:'http://local.test'}};
  const legacy='/enterprise/enterprise.html',assistant='/enterprise/assistant.html';
  const access={navigation:{routes:{[legacy]:{module:'employee_workspace'},[assistant]:{module:'employee_workspace'}},modules:[{id:'employee_workspace',title:'企业智能助手',entry:legacy,pages:[{route:legacy,title:'企业工作台'},{route:assistant,title:'企业智能助手'}]}]}};
  assert.equal(pagePath('/enterprise'),assistant);assert.equal(pagePath('/static'+legacy),assistant);
  assert.equal(loginDestination(legacy,access),assistant);
  assert.deepEqual(visibleModules(access)[0].pages,[{route:assistant,title:'企业智能助手'}]);
  assert.equal(visibleModules(access)[0].entry,assistant);
  delete access.navigation.routes[assistant];assert.equal(visibleModules(access).length,0);
});
