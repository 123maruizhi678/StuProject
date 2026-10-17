# 客服Agent 工作流导入说明

文件 `客服Agent-Chatflow.yml` 是 Dify 的 DSL 导出格式（**工作流**模式，DSL 版本 0.5.0），可在 Dify 控制台「导入 DSL」直接导入。

> 文件名沿用了旧名 `Chatflow`，但实际是 **Workflow（工作流）** 应用，不是 Chatflow。这是为了适配 `/workflows/run` 接口（能拿到 `outputs` 变量），并彻底去掉了导致你之前崩溃的「赋值」节点。

## 一、导入步骤

1. Dify 控制台 → 创建应用 → 选择「**导入 DSL**」。
2. 上传 `客服Agent-Chatflow.yml`。
3. 导入后得到「客服Agent」**工作流**应用。

## 二、导入后必须手动改的 1 处（因我无法连到你的本地环境）

### 1. 模型（1 个意图识别节点 + 7 个 LLM 节点）
DSL 里默认写了 `gpt-4o-mini / openai` 占位。请逐个节点把它换成你在 Dify 里已配置的模型：
- **意图识别**节点（意图识别）：轻量模型即可（省成本，temperature 已设 0.2）
- 其余 7 个「生成话术-xxx」LLM 节点：中等模型
- 若你的 Dify 没配 openai，导入后节点会提示「模型未找到」，选中你自己的模型即可。

### 2. 知识库（已绑定，一般无需再改）
DSL 里 4 个知识检索节点的 `dataset_ids` **已绑定**本地 Dify 的知识库（ID 见 `knowledge/dataset_ids.json`）：

| 节点 | 知识库 | 源文档 |
|:---|:---|:---|
| 知识检索-公司信息 | 公司信息 | `knowledge/公司信息.md` |
| 知识检索-公司业务 | 公司业务 | `knowledge/公司业务.md` |
| 知识检索-留学政策 | 留学政策 | `knowledge/留学政策.md` |
| 知识检索-FAQ | FAQ | `knowledge/FAQ.md` |

> 注意：知识库 ID 与**你这套本地 Dify 环境**绑定。若在别的 Dify 环境重新导入本 DSL，需要按新环境的知识库 ID 重新绑定（改 DSL 里 4 个 `dataset_ids`，或在控制台手动绑）。
> 另：本地 Dify 未配置向量模型，知识库使用**经济索引（关键词检索）**。如需调整关键词召回数量（`keyword_number`），请在 Dify 控制台对应知识库的「检索设置」中修改；后续若配置了 embedding 模型，可在控制台把索引技术升级为「高质量」。

## 二补、知识库内容维护

- 4 份知识库源文档在 `knowledge/` 目录，采用「一问一答 / 分节」结构，`【 】` 为占位符，请替换为机构真实信息。
- **更新流程**：改 `knowledge/*.md` → 控制台删掉旧文档 → 重新上传该文件（自动分段即可）→ 等待索引完成。
- 也可用脚本一键重建：`python scripts/agent/build_dify_kb.py <知识库API密钥>`（密钥在 Dify 控制台「知识库 → API 访问」创建）。
- FAQ 类内容建议保留「Q：/ A：」独立段落结构，保证「一问一段」，检索命中率最高。

## 三、拿到 API Key

1. 导入后进入应用「API 访问」页 → 创建 API 密钥。
2. 复制 `app-xxxx` 填入项目 `.env` 的 `DIFY_AGENT_API_KEY=`。
3. 把 `.env` 的 `DIFY_CLIENT=mock` 改为 `DIFY_CLIENT=real`。

## 四、与后端字段对齐

工作流最终输出 2 个变量，后端 `RealDifyClient` 通过 `/workflows/run` 读取 `data.outputs`：

| Dify 输出 | 后端字段 | 说明 |
|:---|:---|:---|
| intent | ChatResult.intent | 意图分类英文标识（见下表） |
| reply | ChatResult.reply | 最终话术 |

`action` 不再由 Dify 输出，而是后端按 `intent` 推导：

| intent | 后端下发的 action |
|:---|:---|
| course_recommend | `{"type":"show_courses","payload":{}}` |
| event_query | `{"type":"show_events","payload":{}}` |
| 其它 | 无 |

7 个意图标识（即意图识别节点各类别的 `id`）：

| intent | 中文 |
|:---|:---|
| company_info | 公司信息咨询 |
| business_query | 公司业务查询 |
| policy_query | 海外留学政策查询 |
| course_recommend | 课程与项目推荐 |
| event_query | 活动与讲座报名 |
| faq | 常见问题FAQ |
| chat | 日常闲聊 |

## 五、版本兼容提示

本 DSL 已按 Dify 1.12.1 的节点格式生成（`version: 0.5.0`，工作流模式），并已用 1.12.1 的节点实体逐项校验通过。如果你的 Dify 版本不是 1.12.x，导入时若报「版本不兼容 / 节点解析失败」，告诉我你的版本号（控制台左下角或「关于」页），我按你的版本重生成。
