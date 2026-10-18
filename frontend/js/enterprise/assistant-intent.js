/** Choose an existing enterprise endpoint without changing its permission or confirmation rules. */
export function inferEnterpriseIntent(value) {
  const text=String(value||'').trim();
  if(!text)return null;
  // Questions about performing an action belong to the knowledge service.
  if(/怎么|如何|怎样|流程|制度|政策|规定|指南|操作步骤|注意事项|什么意思|是什么|为什么|能否|可不可以|是否可以|需要.{0,8}(权限|材料|条件)/.test(text))return 'knowledge';
  if(/统计|汇总|多少|数量|总数|几条|几位|几名/.test(text)&&!/(并且|并|然后|同时|顺便).{0,30}(新增|修改|更新|删除|归档|作废|分派|提交)/.test(text))return 'query';
  if(/新增|新建|创建|添加|录入|修改|更新|调整|变更|删除|归档|作废|停用|启用|分派|分配|批准|驳回|同意|撤回|记录.{0,8}(日报|跟进)|提交.{0,12}日报|写.{0,4}日报|日报[:：]|把.{1,60}(改成|改为|设为|设置为)|客户.{0,30}(改成|改为|设为)/.test(text))return 'command';
  if(/查询|查找|查一下|查下|查看|查出|检索|统计|汇总|数量|总数|多少|几条|几位|几名|列出|有哪些|有什么|名单|列表|排名|排行|最近.{0,12}(记录|日报|客户|工单)|待处理|待审批|^(所有|全部|本周|本月|今天|昨日|昨天|最近).{0,30}(客户|日报|工单|成绩|学生|课程)/.test(text))return 'query';
  return null;
}
