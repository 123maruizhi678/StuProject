const e='/api/v1/enterprise/',s='/api/v1/student/',i='/api/v1/internal/student/',c='/api/v1/customer/',a='/api/v1/agent/',r='/api/v1/report/';
export const PAGE_RESOURCES={
 'dashboard/dashboard.html':[e+'todos',e+'customer',r+'list'],
 'agent/agent.html':[a+'chat'],'agent/courses.html':[a+'courses'],'agent/events.html':[a+'events'],'agent/event-detail.html':[a+'events'],'agent/faq.html':[a+'faq'],
 'customer/customer.html':[c+'source',c+'result'],'customer/sources.html':[c+'source'],'customer/source-detail.html':[c+'source'],'customer/extract.html':[c+'source'],
 'customer/results.html':[c+'result',c+'judge'],'customer/result-detail.html':[c+'result'],'customer/rules.html':[c+'rule'],'customer/rule-detail.html':[c+'rule'],'customer/products.html':[c+'product'],
 'enterprise/enterprise.html':[e+'todos',e+'customer',e+'daily-report'],'enterprise/assistant.html':[e+'command',e+'onboarding/ask',e+'nl2sql',e+'voice/transcribe'],
 'enterprise/command-preview.html':[e+'command'],'enterprise/query.html':[e+'nl2sql'],'enterprise/customers.html':[e+'customer'],'enterprise/customer-detail.html':[e+'customer'],'enterprise/followups.html':[e+'customer'],
 'enterprise/daily-reports.html':[e+'daily-report'],'enterprise/daily-report-new.html':[e+'daily-report'],'enterprise/daily-report-detail.html':[e+'daily-report'],'enterprise/todos.html':[e+'todos',e+'notifications'],
 'enterprise/organization.html':[e+'organization',e+'departments',e+'employees'],'enterprise/bindings.html':[e+'student-bindings'],'enterprise/students.html':[e+'students'],'enterprise/student-detail.html':[e+'students'],
 'enterprise/scores.html':[e+'scores'],'enterprise/academics.html':[e+'academic-events',i+'academic'],'enterprise/courses.html':[e+'courses',e+'student-courses'],'enterprise/application-progress.html':[e+'application-progress',i+'progress'],
 'enterprise/leave-review.html':[i+'leave'],'enterprise/leave-detail.html':[i+'leave'],'enterprise/tickets.html':[e+'tickets'],'enterprise/ticket-detail.html':[e+'tickets'],
 'enterprise/knowledge.html':[e+'knowledge',e+'onboarding/ask'],'enterprise/knowledge-detail.html':[e+'knowledge'],'enterprise/warnings.html':[i+'warnings'],'enterprise/warning-detail.html':[i+'warnings'],
 'student/student-assistant.html':[s+'academic',s+'progress',s+'notifications'],'student/chat.html':[s+'chat',s+'actions/confirm'],'student/academics.html':[s+'courses',s+'scores',s+'academic'],
 'student/progress.html':[s+'progress'],'student/reminders.html':[s+'reminders'],'student/leave.html':[s+'leave'],'student/leave-detail.html':[s+'leave'],
 'student/tickets.html':[s+'tickets',s+'complaint'],'student/ticket-detail.html':[s+'tickets'],'student/notifications.html':[s+'notifications'],'student/care.html':[s+'mental/monitor'],'student/action-preview.html':[s+'actions/confirm'],
 'report/report.html':[r+'list',r+'generate'],'report/list.html':[r+'list'],'report/generate.html':[r+'generate'],'report/detail.html':[r+'{report_record_id}'],'report/configs.html':[r+'configs'],
 'common/account.html':['/api/v1/auth/me/access',e+'me/permissions'],'common/notifications.html':[e+'notifications',s+'notifications',i+'notifications'],
 'admin/accounts.html':['/api/v1/admin/accounts','/api/v1/auth/register'],'admin/permissions.html':['/api/v1/auth/me/access',e+'me/permissions',e+'employees'],'admin/audit.html':[e+'operation-logs'],'admin/settings.html':[r+'configs'],
};
export function operationsForPage(page,paths){
 return Object.entries(paths).flatMap(([path,methods])=>(PAGE_RESOURCES[page]||[]).some(prefix=>path===prefix||path.startsWith(prefix+'/'))
 ?Object.entries(methods).filter(([method])=>['get','post','put','delete','patch'].includes(method)).map(([method,operation])=>({method:method.toUpperCase(),path,...operation})):[])
 .sort((a,b)=>{
  const rank=op=>op.method==='GET'&&!op.path.includes('{')?0:op.method==='POST'&&!op.path.includes('{')?1:op.method==='GET'?2:3;
  return rank(a)-rank(b)||a.path.split('/').length-b.path.split('/').length;
 });
}

// 菜单与表单均采用服务端精确动作权限，查看资料不隐含解析或原件下载权限。
export function operationsForAccess(operations, access) {
 const permissions = new Set(access?.permissions || []);
 return operations.filter(operation => {
  const { path, method } = operation;
  let permission;
  if (path.startsWith('/api/v1/customer/')) {
   if (method === 'GET') permission = path.endsWith('/file') ? 'customer.source.file'
    : path.includes('/source') ? 'customer.source.read'
    : path.includes('/result') ? 'customer.result.read' : 'customer.rule.read';
   else if (path.includes('/parse')) permission = 'customer.source.parse';
   else if (path.endsWith('/source')) permission = 'customer.source.create';
   else if (path.endsWith('/judge/batch')) permission = 'customer.judge.batch';
   else if (path.endsWith('/judge')) permission = 'customer.judge.create';
   else if (path.endsWith('/rule')) permission = 'customer.rule.manage';
   else return false;
  } else if (path.startsWith('/api/v1/report/')) {
   permission = path.includes('/configs') ? (method === 'GET' ? 'report.config.read' : 'report.config.write')
    : path.endsWith('/generate') && method === 'POST' ? 'report.generate'
    : method === 'GET' ? 'report.read' : null;
   if (!permission) return false;
  } else return true;
  return permissions.has(permission);
 });
}
export const LABELS={
 announcement_id:'公告编号',pinned:'置顶',published_at:'发布时间',author_user_id:'发布人编号',message_key:'消息标识',
 status_changed_at:'状态变更时间',last_followup_at:'最近跟进时间',external_updated_at:'外部更新时间',is_archived:'是否归档',
 id:'记录编号',type:'类型',version:'当前版本',version_no:'内容版本号',ai_summary:'辅助摘要',submitted_at:'提交时间',department_id_at_submit:'提交时所属部门',
 acknowledged_at:'接手时间',closed_at:'关闭时间',finished_at:'完成时间',observed_at:'消息发生时间',analysis_version:'分析版本',
 apply_content:'申请内容',apply_type:'申请类型',edu_related_data:'教务相关资料',course_scope_code:'授权课程编码',
 emotion_score:'情绪评分',emotion_tag:'情绪标签',risk_level:'风险等级',trigger_reason:'触发原因',follower_id:'处理员工编号',follower_status:'跟进处理状态',handling_result:'处理结果',profile_id:'评估记录编号',history_data:'历史评估记录',
 external_application_id:'外部申请编号',external_document_id:'外部文档编号',external_employee_id:'外部员工编号',external_event_id:'外部事项编号',external_request_id:'外部请求编号',external_student_id:'外部学生编号',external_customer_id:'外部客户编号',crm_student_id:'客户管理系统学生编号',
 source_event_id:'来源事件编号',source_system:'来源系统',source_timezone:'来源时区',source_updated_at:'来源更新时间',synced_at:'同步时间',workflow_run_id:'工作流运行编号',
 ticket_no:'工单编号',ticket_record_id:'工单处理记录编号',priority:'优先级',handling_department_id:'处理部门编号',first_response_at:'首次响应时间',response_due_at:'响应截止时间',resolution_due_at:'解决截止时间',solution:'解决方案',resolved_at:'解决时间',reopen_count:'重新打开次数',cycle_no:'处理轮次',to_status:'处理后状态',record_type:'记录类型',record_key:'记录去重标识',service_code:'服务编码',sla_snapshot:'服务时限快照',
 index_status:'知识索引状态',reviewer_employee_id:'审核员工编号',delivery_status:'发送状态',attempt_count:'尝试发送次数',next_retry_at:'下次重试时间',lease_until:'任务占用截止时间',last_error_code:'最近错误编码',dedupe_key:'通知去重标识',
 notify_at:'计划提醒时间',schedule_base_at:'提醒基准时间',schedule_operation_id:'提醒安排操作编号',
 operation_log_id:'操作记录编号',operation_key:'操作唯一标识',change_reason:'变更原因',error_code:'错误编码',before_data:'变更前数据',after_data:'变更后数据',result_reference:'操作结果',
 records:'相关记录',items:'记录列表',rows:'查询结果',columns:'结果字段',total:'记录总数',count:'数量',unread_count:'未读数量',unread:'未读状态',tree:'组织层级',kind:'业务类型',
 citations:'引用资料',sources:'资料来源',confidence:'可信度',needs_clarification:'是否需要补充说明',clarification:'补充说明',intent:'业务意图',collaboration:'协作说明',auto_merge:'是否自动合并',
 mode:'回答方式',missing_fields:'待补充字段',expires_in:'有效时长（秒）',resource:'业务对象',candidates:'候选记录',authorized_targets:'可操作对象',contract_version:'业务契约版本',sql:'查询语句',truncated:'是否已截断',parameters:'业务参数',success:'是否成功',
 policy_version:'策略版本',started_at:'开始时间',hours:'服务时限',clock:'计时方式',response_hours:'响应时限（小时）',resolution_hours:'解决时限（小时）',row_count:'结果记录数',schema_version:'数据结构版本',
 customer_no:'客户编号',source_channel:'来源渠道',authority_source:'维护来源',employee_name:'员工姓名',
 product_name:'产品名称',source_type:'资料类型',file_name:'文件名称',matched:'是否符合条件',score:'研判得分',
 matched_fields:'符合条件的字段',unmatched_reasons:'不符合原因',input_snapshot:'研判依据',
 event_name:'活动名称',start_time:'开始时间',location:'地点',signup_method:'报名方式',quota:'名额',signed_count:'已报名人数',
 description:'介绍',target_audience:'适用人群',category:'类别',sent_at:'发布时间',read_at:'已读时间',
 event_code:'业务事件',entity_type:'业务类型',entity_id:'业务编号',operation_status:'处理状态',action_code:'业务动作',
 approval_comment:'审批意见',reviewer_id:'审批人',reviewed_at:'审批时间',report_content:'报告正文',metric_json:'统计指标',
 fail_reason:'未完成原因',source_record_count:'统计记录数',ai_status:'辅助分析状态',assignment_pending:'待分派',
 username:'账号',identity_type:'账号身份',profile:'业务档案',full_name:'姓名',employee_no:'员工编号',student_no:'学号',department_id:'部门编号',employee_id:'员工编号',student_id:'学生编号',customer_id:'客户内部编号',position_title:'职位',
 customer:'客户档案',source:'资料来源',result:'研判结果',rule:'研判规则',product:'产品','daily-report':'工作日报',students:'学生档案',scores:'学生成绩',courses:'课程','student-courses':'学生选课','academic-events':'学业节点','application-progress':'申请进度',
 tickets:'服务工单',knowledge:'知识资料',notifications:'通知',employees:'员工',departments:'部门','student-bindings':'学生服务关系','operation-logs':'操作记录',todos:'待办',organization:'组织结构',leave:'请假',warnings:'关怀跟进',reminders:'学业提醒',academic:'学业节点',progress:'申请进度',
 configs:'报告配置',generate:'生成报告',list:'报告列表',chat:'智能对话',complaint:'提交反馈',command:'工作指令',confirm:'确认办理',ask:'知识问答',nl2sql:'业务查询',transcribe:'语音转文字',accounts:'账号',register:'创建账号',options:'开户选项',permissions:'权限',access:'访问权限',
 followups:'跟进记录',schedule:'跟进安排',assign:'分派',roles:'角色',publish:'发布',resolve:'解决方案',reply:'回复',rating:'评价',decision:'审批决定',read:'标记已读',summary:'日报摘要',file:'原件下载',judge:'客户研判',batch:'批量研判',parse:'字段解析',events:'活动',signup:'活动报名',faq:'常见问题',monitor:'心情评估',ack:'接手',follow:'跟进',close:'关闭',assignments:'待接管清单','phone-candidates':'按电话查询客户',
 report_code:'报告类型',report_record_id:'报告编号',report_name:'报告名称',report_period:'报告周期',report_id:'日报编号',daily_report_id:'日报编号',report_date:'日报日期',submitted_content:'工作内容',course_id:'课程编号',course_code:'课程编码',course_name:'课程名称',term_code:'学期编码',assessment_code:'考核项目',attempt_no:'考试次数',score_id:'成绩编号',score_value:'成绩',max_score:'满分',enrollment_id:'选课编号',
 report_config_id:'报告配置编号',report_version:'报告版本',data_snapshot_at:'指标快照时间',generated_at:'生成完成时间',idempotency_key:'幂等键',
 event_id:'活动编号',academic_event_id:'学业节点编号',event_type:'节点类型',title:'标题',due_at:'截止时间',event_status:'节点状态',event_version:'节点版本',expected_event_version:'当前节点版本',progress_id:'进度编号',application_name:'申请名称',stage_code:'申请阶段',stage_status:'阶段状态',detail:'说明',binding_id:'关系编号',relation_type:'服务关系',is_primary:'是否主负责人',valid_from:'生效时间',valid_to:'结束时间',
 department_code:'部门编码',department_name:'部门名称',parent_department_id:'上级部门编号',function_description:'部门职责',login_provider:'登录来源',login_subject:'登录标识',joined_date:'入职日期',left_date:'离职日期',work_email:'工作邮箱',role_codes:'业务角色',phone:'联系电话',education_level:'学历',target_country_code:'意向国家编码',status:'状态',content:'内容',channel:'渠道',followup_at:'跟进时间',next_followup_at:'下次跟进时间',followup_id:'跟进编号',followup_status:'跟进状态',reason:'操作原因',lost_reason:'流失原因',
 row_version:'当前版本',expected_version:'当前版本',created_at:'创建时间',updated_at:'更新时间',expected_updated_at:'当前更新时间',entry_code:'知识编码',entry_type:'资料类型',question:'问题',answer:'答案',content_text:'资料正文',knowledge_id:'知识编号',effective_from:'生效时间',expires_at:'失效时间',source_reference:'资料来源',access_department_id:'可访问部门',message:'咨询内容',user_id:'用户编号',session_id:'会话编号',conversation_token:'会话凭证',text:'文字内容',token:'确认凭证',action:'办理事项',action_token:'办理凭证',target:'办理对象',fields:'确认内容',filters:'筛选条件',chat_content:'心情描述',
 leave_content:'请假事由',leave_type:'请假类型',leave_start_at:'开始时间',leave_end_at:'结束时间',generate_ai_summary:'生成辅助摘要',apply_id:'请假编号',approval_status:'审批状态',comment:'处理意见',ticket_id:'工单编号',ticket_type:'反馈类型',category_code:'问题分类',visibility:'可见范围',resolved:'问题已解决',satisfaction_score:'满意度评分',notification_id:'通知编号',warning_id:'关怀记录编号',note:'处理记录',lead_minutes:'提前分钟数',reminder_id:'提醒编号',
 start_time:'开始时间',end_time:'结束时间',timezone:'时区',enabled:'是否启用',cron_expr:'自动生成时间',source_id:'来源编号',force:'重新解析',customer_info_id:'客户字段编号',customer_info_ids:'客户字段编号列表',product_code:'产品编码',rule_version:'规则版本',rule_content:'研判条件',rule_description:'规则说明',is_active:'是否生效',effective_to:'失效时间',customer_name:'报名姓名',customer_phone:'报名电话',customer_info:'补充信息',q:'查询关键词',keyword:'关键词',limit:'每页数量',offset:'起始位置',page:'页码',page_size:'每页数量',unread_only:'只看未读',manage:'管理全部版本',
};
