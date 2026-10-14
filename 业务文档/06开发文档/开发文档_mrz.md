```markdown
# 智能报告 开发文档

## 一、项目概述

### 1.1 项目名称
智能报告模块

### 1.2 项目目标
建设智能报告体系，覆盖全域客户经营分析报告、员工日报汇总报告（日/周）、学生心理健康周报、投诉处理周报等，通过AI智能汇总与分析，将碎片化数据转化为结构化、可视化的决策支持报告。

### 1.3 技术栈
- AI编排平台：Dify
- 后端框架：FastAPI
- 数据库：MySQL
- 定时任务：Celery / APScheduler
- 报告生成：LLM + 模板引擎

### 1.4 核心架构
用户浏览器
    ↓
Nginx 前端页面（http://192.168.5.12）
    ↓
FastAPI 后端服务（/api/）
    ↓
Dify 多智能体（http://192.168.5.12/apps）
    ├── 客户经营分析智能体
    ├── 员工日报汇总智能体
    ├── 学生心理健康智能体
    └── 投诉处理智能体
    ↓
MySQL 数据库
---

## 二、开发环境

### 2.1 通过 environment.yml 创建 conda 环境
conda env create -f environment.yml

### 2.2 激活环境
conda activate SST

### 2.3 验证环境(SST * D:\anaconda3\envs\SST)
conda env list

---

## 三、Dify 调用

### 3.1 方案说明
采用方案：每个核心功能做一个智能体，API后端分别调用。
在 Dify 中为每个核心功能创建独立智能体，FastAPI 后端按报告类型分别调用对应智能体，实现职责清晰、独立维护、数据隔离、扩展性强。

### 3.2 智能体划分
智能体名称	对应功能	调用地址
客户经营分析智能体	全域客户经营分析报告	http://192.168.5.12/apps/customer-analysis
员工日报汇总智能体	员工日报汇总报告（日/周）	http://192.168.5.12/apps/daily-report
学生心理健康智能体	学生心理健康周报	http://192.168.5.12/apps/mental-health
投诉处理智能体	投诉处理周报	http://192.168.5.12/apps/complaint

### 3.3 调用地址
Dify 应用调用地址：http://192.168.5.12/apps
调用方式：HTTP / HTTPS

### 3.4 调用流程说明
步骤一：获取各智能体 API Key
登录 Dify 平台
分别进入四个智能体应用
在「API 访问」中获取各自 API Key
记录 API Base URL：http://192.168.5.12/apps

步骤二：FastAPI 封装 Dify 调用
在 FastAPI 中创建 dify_client.py
通过 HTTP 请求调用对应智能体接口
请求头携带 Authorization: Bearer {DIFY_API_KEY}
请求体传入报告类型、数据源等参数
根据 report_type 路由到不同智能体

步骤三：调用示例
'''
import requests
DIFY_BASE_URL = "http://192.168.5.12/apps"

DIFY_AGENTS = {
    "customer_analysis": {
        "url": f"{DIFY_BASE_URL}/customer-analysis/v1/workflows/run",
        "api_key": "customer-analysis-api-key"
    },
    "daily_report": {
        "url": f"{DIFY_BASE_URL}/daily-report/v1/workflows/run",
        "api_key": "daily-report-api-key"
    },
    "mental_health": {
        "url": f"{DIFY_BASE_URL}/mental-health/v1/workflows/run",
        "api_key": "mental-health-api-key"
    },
    "complaint": {
        "url": f"{DIFY_BASE_URL}/complaint/v1/workflows/run",
        "api_key": "complaint-api-key"
    }
}

def call_dify_agent(report_type: str, data: dict):
    agent = DIFY_AGENTS.get(report_type)
    if not agent:
        raise ValueError(f"未知报告类型: {report_type}")

    headers = {
        "Authorization": f"Bearer {agent['api_key']}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": {
            "report_type": report_type,
            "data": data
        },
        "response_mode": "blocking",
        "user": "system"
    }
    response = requests.post(agent["url"], json=payload, headers=headers)
    return response.json()
'''

步骤四：返回结果处理
解析对应智能体返回的报告内容
存入 report_record 表
返回给前端页面展示

## 四、FastAPI 配置

### 4.1 项目结构
```
smart_report/
├── app/
│   ├── main.py
│   ├── api/
│   │   └── report.py
│   ├── services/
│   │   ├── dify_client.py
│   │   ├── report_service.py
│   │   ├── data_collector.py
│   │   └── report_generator.py
│   ├── tasks/
│   │   └── scheduled_tasks.py
│   ├── models/
│   ├── schemas/
│   ├── core/
│   │   └── config.py
│   └── db/
│       └── session.py
├── requirements.txt
├── .env
└── README.md
```

### 4.2 环境变量配置（.env）
| 变量名 | 说明 | 实际值 |
|:---|:---|:---|
| DIFY_BASE_URL | Dify服务地址（http://192.168.5.12/apps） | |
| DIFY_API_KEY_CUSTOMER | 客户经营分析智能体API Key | |
| DIFY_API_KEY_DAILY | 员工日报汇总智能体API Key | |
| DIFY_API_KEY_MENTAL | 学生心理健康智能体API Key | |
| DIFY_API_KEY_COMPLAINT | 投诉处理智能体API Key | |
| MYSQL_HOST | 192.168.5.12 | |
| MYSQL_PORT | 3306 | |
| MYSQL_USER | root | |
| MYSQL_PASSWORD | 12345 | |
| MYSQL_DATABASE | smart_report | |

### 4.3 启动配置
| 配置项 | 说明 | 实际值 |
|:---|:---|:---|
| 服务端口 | 8000 | |
| 日志级别 | info | |

---

## 五、MySQL 配置

### 5.1 数据库配置
| 配置项 | 说明 | 实际值 |
|:---|:---|:---|
| 数据库名 | smart_report | |
| 字符集 | utf8mb4 | |
| 排序规则 | utf8mb4_unicode_ci | |
| 连接池大小 | 待填写 | |

### 5.2 数据表
- report_config：报告配置表
- report_record：报告生成记录表

---

## 六、核心功能开发

### 6.1 全域客户经营分析报告
- 覆盖意向、成交及流失三大核心客群
- 意向客户：新增数量及同环比趋势、特征聚类画像
- 成交客户：转化路径与高价值特征复盘
- 流失客户：智能归因与流失风险预警
- 对应智能体：客户经营分析智能体

### 6.2 员工日报智能汇总报告
- 日、周多维时间粒度
- AI提取核心进展、关键产出及潜在风险
- 结构化工作简报生成
- 对应智能体：员工日报汇总智能体

### 6.3 学生心理健康周报
- 基于情绪打卡、学业压力反馈、跨文化适应情况
- AI汇总心理态势，识别风险群体
- 情绪波动趋势分析与个性化建议
- 对应智能体：学生心理健康智能体

### 6.4 投诉处理周报
- 投诉总量及同环比变化
- AI智能分类
- 跟进状态、处理时效及满意度追踪
- 长期未决案件预警
- 对应智能体：投诉处理智能体

---

## 七、接口开发

| 接口 | 方法 | 说明 |
|:---|:---|:---|
| /report/generate | POST | 生成报告 |
| /report/{id} | GET | 查询报告 |
| /report/list | GET | 查询报告列表 |

---

## 八、部署配置(待定)

### 8.1 Docker 配置
| 配置项 | 说明 | 实际值 |
|:---|:---|:---|
| 镜像名称 | 待填写 | |
| 容器端口 | 待填写 | |
| 挂载目录 | 待填写 | |

### 8.2 Docker Compose 配置
| 服务 | 说明 | 实际值 |
|:---|:---|:---|
| fastapi | 后端服务 | |
| mysql | 数据库 | |
| redis | 缓存/消息队列 | |
| celery | 定时任务 | |
| dify | AI编排平台 | |

---

## 九、测试配置(待定)

| 测试类型 | 说明 | 实际值 |
|:---|:---|:---|
| 单元测试 | pytest | |
| 接口测试 | Postman | |
| 报告准确性测试 | 数据一致性测试 | |
| 覆盖率要求 | 待填写 | |

---