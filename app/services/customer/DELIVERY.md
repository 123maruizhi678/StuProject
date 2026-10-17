# 客户研判模块 · 交付包

客户研判模块的完整交付：**FastAPI 后端**（分层架构）+ **Dify 资产**（字段抽取工作流 + 规则知识库）+
**科技风前端**（主门户 + 客户研判单页）。

## 一、目录结构

```
sgt生成文件/
├── app/                          # 后端（FastAPI 分层架构）
│   ├── main.py                   # 应用入口，注册路由 / 异常 / CORS
│   ├── config.py                 # 配置（.env 加载）
│   ├── database.py               # 唯一 Base、连接池、会话
│   ├── access_control.yaml       # 身份 -> 权限 -> 页面/模块
│   ├── api/
│   │   ├── common/auth.py        # 登录 / 访问信息
│   │   └── customer/customer.py  # 客户研判 9 接口
│   ├── core/common/              # response / auth / authorization / security / dify / logger
│   ├── schemas/                  # 请求响应契约（pydantic）
│   ├── services/                 # 业务编排（auth / parser / extractor / judge / customer）
│   ├── repositories/             # 数据访问（SQL）
│   ├── models/                   # ORM 模型（common 共享 + customer 5 表）
│   └── clients/customer/         # Dify 字段抽取客户端
├── sql/customer_schema.sql       # 5 张业务表参考 DDL
├── scripts/
│   ├── seed_demo.py              # 演示数据（账号/产品/规则）
│   └── create_knowledge_base.py  # 一键创建 Dify 知识库
├── dify/customer/
│   ├── customer-extract.yml      # 客户字段抽取 Workflow（DSL 导出，可导入）
│   ├── README.md
│   └── knowledge/客户画像研判规则.md
├── frontend/                     # 科技风前端（HTML+CSS+JS）
│   ├── index.html                # 主门户（调用各模块页面）
│   ├── css/common/style.css      # 统一科技主题
│   ├── css/customer/customer.css
│   ├── js/common/{api.js,effects.js}
│   └── customer/{customer.html} + js/customer/customer.js
├── test_customer_api.py          # 9 接口端到端测试
├── requirements.txt
├── .env / .env.example
└── README.md
```

## 二、接口清单（统一信封 `{code, message, data}`，code=0 成功）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | `/api/v1/auth/login` | 公开 | 登录换取 JWT |
| GET  | `/api/v1/auth/me` | 登录 | 当前账号权限 |
| POST | `/api/v1/customer/source` | `customer.source.create` | 来源登记（文本/文件） |
| POST | `/api/v1/customer/source/{id}/parse` | `customer.source.parse` | 解析入库 |
| GET  | `/api/v1/customer/source/{id}/file` | `customer.source.file` | 受控原件下载 |
| POST | `/api/v1/customer/judge` | `customer.judge.create` | 单条研判 |
| POST | `/api/v1/customer/judge/batch` | `customer.judge.batch` | 批量研判 |
| GET  | `/api/v1/customer/result/{id}` | `customer.result.read` | 结果详情 |
| GET  | `/api/v1/customer/result` | `customer.result.read` | 结果分页查询 |
| GET  | `/api/v1/customer/rule` | `customer.rule.read` | 规则列表 |
| PUT  | `/api/v1/customer/rule` | `customer.rule.manage` | 发布新规则版本 |

### 角色权限

| 账号 | 身份 | 角色 | 权限 |
|------|------|------|------|
| cust_admin | admin | - | 全部客户研判权限 |
| analyst | employee | analyst | 来源登记/解析、研判/批量研判、原件下载 |
| reviewer | employee | reviewer | 规则读取、结果读取 |
| consultant | employee | consultant | 结果读取 |

演示密码统一 `123456`（由 `scripts/seed_demo.py` 生成）。

## 三、快速启动

```bash
# 1. 依赖
pip install -r requirements.txt

# 2. 配置（复制 .env.example 为 .env，填入数据库 / Dify / 密钥）

# 3. 演示数据（产品、规则、账号）
python scripts/seed_demo.py

# 4. 启动后端
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 5. 端到端测试
python test_customer_api.py

# 6. 前端：浏览器直接打开 frontend/index.html（或任意静态服务器）
```

## 四、关键设计

- **确定性规则引擎**：`rule_content`（conditions + score_rules + score_threshold）由后端确定性执行，
  命中/未命中均为正常业务结果；无有效规则、产品停用、规则格式错误时不生成正常结论。
- **Dify 仅辅助抽取**：`customer-extract.yml`（DeepSeek deepseek-flash）抽取非结构化文本的语义字段，
  确定性电话/邮箱提取优先；`CUSTOMER_EXTRACT_DIFY_API_KEY` 为空时降级为纯确定性路径。
- **数据保护**：电话仅存 AES-GCM 密文 + HMAC 检索 token；邮箱仅存掩码；原始文件非公网受控定位键。
- **权限**：JWT 确认身份，接口权限以服务端 `access_control.yaml` + 员工 `role_codes` 为准；
  未认证 401、无权限 403。
- **批量隔离**：批量研判逐条 savepoint，单条失败不影响整批。

## 五、Dify 资产（已在本机配置）

- **客户信息抽取** Workflow：已发布，API Key 已写入 `.env`（`CUSTOMER_EXTRACT_DIFY_API_KEY`）。
- **客户画像研判规则** 知识库：已创建（economy 索引），导入规则语义文档。
- **DeepSeek**：模型提供商 API Key 已更新为团队密钥（`deepseek-flash`）。
