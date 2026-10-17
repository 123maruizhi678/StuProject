-- =============================================================
-- 客服 Agent 六表测试数据（少量，用于库内查看与接口联调）
-- 结构依据：开发文档/操作文档_数据库建表语句.sql 的 006—011 表
--   course_project / lecture_event / event_signup / faq / chat_session / chat_message
--
-- 前置：目标库已按建表语句创建六表（含外键 fk_signup_event / fk_message_session）。
-- 外键插入顺序：course_project → lecture_event → faq → chat_session → event_signup → chat_message
--
-- 注意：
--   1. 本脚本面向空表；自增 ID 从 1 开始，故 event_signup 的 event_id 取 1（第一个活动）。
--      若库内已有数据，请把 event_id / session_id 改成实际存在的值。
--   2. 时间字面量按后端现有实现口径直接入库；若库已统一 UTC 存储，请自行换算。
--   3. 报名数据设计为“1 有效 + 1 取消”，用于验证状态式判重（取消不阻挡重报）。
-- =============================================================

-- ---------- 课程（3 条：2 上架 + 1 下架；验证“仅上架对访客可见”） ----------
INSERT INTO course_project (course_name, category, target_audience, description, location, signup_method, status) VALUES
  ('雅思 6.5 分冲刺班', '语言培训', '计划留学英联邦国家的学生', '听力阅读写作口语四项强化，考前模考与逐句批改。', '线上直播', '咨询顾问老师报名', '上架'),
  ('新加坡本硕升学规划', '留学申请', '专科 / 本科在读学生', '2+2、0.5+2 等班型评估，院校申请材料指导。', '本部校区', '咨询顾问老师报名', '上架'),
  ('PTE 冲刺 65 分班', '语言培训', '希望快速出分的学生', '旧版班型，暂停招生。', '线上直播', '咨询顾问老师报名', '下架');

-- ---------- 活动（2 条：1 个限名额且已有 1 人报名 + 1 个不限名额） ----------
INSERT INTO lecture_event (event_name, event_type, start_time, location, signup_method, quota, signed_count, status) VALUES
  ('德国双元制招生官见面会', '线上', '2026-11-08 19:30:00', '线上直播间', '页面在线报名', 100, 1, '报名中'),
  ('新加坡升学路径公开课', '线上', '2026-11-15 19:30:00', '线上直播间', '页面在线报名', 0, 0, '报名中');

-- ---------- FAQ（3 条） ----------
INSERT INTO faq (question, answer, category) VALUES
  ('留学申请的整体流程是什么？', '流程一般为：背景评估 → 选校定专业 → 材料准备（成绩单、推荐信、个人陈述）→ 递交申请 → 面试 → 录取与签证。全程由顾问老师跟进。', '申请流程'),
  ('服务费用如何收取？', '费用按服务内容分档收取，具体以签约时顾问老师提供的明细为准，所有收费项目均会提前书面确认。', '服务费用'),
  ('报名讲座和活动收费吗？', '公开讲座与线上活动免费，线下活动名额有限，以页面显示状态为准；报名成功后会发送确认通知。', '活动报名');

-- ---------- 会话（2 个） ----------
INSERT INTO chat_session (session_id, user_id, channel) VALUES
  ('test-session-0001', 'visitor-0001', 'web'),
  ('test-session-0002', '', 'web');

-- ---------- 报名（2 条：event_id=1 即第一个活动；1 有效 + 1 取消） ----------
INSERT INTO event_signup (event_id, customer_name, customer_phone, customer_info, source, status) VALUES
  (1, '张三', '13800000001', JSON_OBJECT('target_country', 'DE', 'education_level', '本科'), '客服对话', '有效'),
  (1, '李四', '13800000002', NULL, '客服对话', '取消');

-- ---------- 消息（4 条，挂 test-session-0001：含 user / assistant 两种角色） ----------
INSERT INTO chat_message (session_id, role, intent, content) VALUES
  ('test-session-0001', 'user', '', '最近有什么留学讲座？'),
  ('test-session-0001', 'assistant', 'event_query', '近期有以下留学讲座，您可以直接在下方报名～'),
  ('test-session-0001', 'user', '', '我想了解新加坡的升学路径'),
  ('test-session-0001', 'assistant', 'policy_query', '新加坡升学路径公开课将在 11 月 15 日举行，欢迎在下方报名参加。');

-- =============================================================
-- 查看语句（逐表执行或一次性执行均可）
-- =============================================================

-- 课程：应见 3 条，其中 2 条 status='上架'
SELECT id, course_name, category, status, created_at FROM course_project ORDER BY id;

-- 活动：应见 2 条；第一条 signed_count=1（对应 1 条有效报名）
SELECT id, event_name, event_type, start_time, quota, signed_count, status FROM lecture_event ORDER BY id;

-- FAQ：应见 3 条
SELECT id, LEFT(question, 24) AS question, category FROM faq ORDER BY id;

-- 会话：应见 2 个
SELECT id, session_id, user_id, channel FROM chat_session ORDER BY id;

-- 报名：应见 2 条（1 有效 + 1 取消），且与活动 1 关联
SELECT s.id, s.event_id, e.event_name, s.customer_name, s.customer_phone, s.status, s.signup_time
FROM event_signup s JOIN lecture_event e ON e.id = s.event_id ORDER BY s.id;

-- 消息：应见 4 条，按时间正序；role 含 user / assistant
SELECT m.id, m.session_id, m.role, m.intent, LEFT(m.content, 30) AS content_prefix, m.created_at
FROM chat_message m ORDER BY m.created_at, m.id;

-- 报名计数对账：有效报名数应与 lecture_event.signed_count 一致（=1）
SELECT e.id, e.event_name, e.signed_count,
       (SELECT COUNT(*) FROM event_signup s WHERE s.event_id = e.id AND s.status = '有效') AS active_signups
FROM lecture_event e ORDER BY e.id;
