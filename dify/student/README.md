# 学生助手 Dify 配置

此目录只包含学生模块的Prompt和结构契约，不包含任何密钥。需要在实际Dify实例配置并发布三个应用，填写独立Key后才能真实联调；没有配置时后端返回503，不使用模拟AI冒充真实结果。

## 应用一：学生助手 Chatflow

1. 创建Chatflow，开启引用来源展示。
2. 问题分类器分为七类：leave、mental、feedback、academic、progress、life、upgrade。
3. life分支检索“海外生活指南”；upgrade分支检索“升学项目资料”。其他分支可直达模型节点。
4. 每个分支模型节点使用chat_prompt.md，使用chat.schema.json约束结构化输出。每次输出都包含mental评估，包括非mental分支。
5. Answer节点输出完整JSON字符串，而不是额外包裹自然语言；保留RAG引用到API metadata.retriever_resources。
6. 发布后将应用Key填入STUDENT_DIFY_CHAT_KEY。

后端调用 /chat-messages，使用blocking模式和绑定学生身份的user；会话ID由后端签名绑定，不接受任意学生身份。此版本使用Chatflow，不使用仅支持流式响应的Agent应用。[Dify对话API](https://docs.dify.ai/en/api-reference/chat-messages/send-chat-message)

## 应用二：心理评估 Workflow

Start节点定义字符串输入text → 模型节点使用mental_prompt.md和mental.schema.json → End节点定义result，映射为模型的结构化对象（或可解析JSON字符串）。发布后填入STUDENT_DIFY_MENTAL_KEY。

## 应用三：投诉摘要 Workflow

Start输入text → 模型节点使用ticket_prompt.md和ticket.schema.json → End输出result。发布后填入STUDENT_DIFY_TICKET_KEY。摘要失败不阻止学生提交原始反馈。

后端工作流调用 /workflows/run，要求data.status=succeeded，读取data.outputs.result。[Dify Workflow概览](https://docs.dify.ai/en/api-reference/guides/workflow)

## 知识材料

| 知识库 | 必需内容 | 导入要求 |
|---|---|---|
| 海外生活指南 | 实际服务国家的医疗、交通、住宿、紧急求助等资料 | 标明国家/地区、来源、版本及有效期 |
| 升学项目资料 | 机构当前真实课程、硕博项目、条件与联系途径 | 标明项目编号、更新日期及在售状态 |

仓库目前没有这些原文，必须由业务方提供，不能把示例当成事实导入。检索不到来源时后端统一提示联系服务老师核实。

## 发布前人工评测

至少准备每类10条真实脱敏问法；检查七类路由、缺参数澄清、跨分支高危识别、无召回拒绝编造、恶意指令不触发写库、推荐仅使用有效项目。目标路由准确率沿用需求文档不低于90%。记录样本、实际答案、版本与结果；当前自动化测试不等同于这些真实AI评测。
