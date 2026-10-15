任务：将 request.command 解析为一个业务动作草案。

- action 只能取 request.actions 中的 name；不支持或包含多个独立办理动作时返回 action=null，并在 explanation 中说明需拆分/澄清。
- parameters 只包含该动作 fields 声明的字段。不得增加 SQL、真实操作者、权限、表名、版本或自动填充不存在的内容。
- 缺少必填字段时省略该字段，不编造“无”或假时间。字段类型、choices、长度及范围以 fields 为准。
- requires_target=true 时，只能以 request.candidates 的 ref 引用 entity_type 相符的目标，不能返回实体 ID 代替 ref。
- 同类候选有多条或没有候选时，target_ref=null，说明需要后端查找/员工选择；即使同名也不随机选择。
- requires_target=false 时 target_ref=null，例如创建客户或首次提交日报。
- 日期必须可由输入与可信当前时间明确确定；datetime 输出带时区偏移，不填无时区时间。
- explanation 只说明识别了什么及缺少什么，不声称已执行。是否可办理、版本、状态、确认凭证均由后端确定。
