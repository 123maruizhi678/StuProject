下面是一份可落地的设计方案，按“总体思路 → 数据库 → 角色权限 → 接口 → 目录架构 → 研判流程”展开。核心原则是：**产品可扩展、规则可配置、规则版本可追溯、客户信息可解析、研判结果可复核**。

---

## 一、总体设计思路

### 1. 核心链路
```text
客户信息录入/上传（文本、PDF、Excel）
        ↓
文件解析 + 字段抽取
        ↓
客户结构化画像
        ↓
加载产品已发布规则版本
        ↓
规则引擎执行：硬性规则 + 评分规则
        ↓
输出：符合 / 不符合 / 待人工复核
        ↓
结果查看、导出、人工复核、统计
```

### 2. 规则模型
建议采用：
```text
产品 Product
  └── 规则版本 RuleVersion
        └── 规则组 RuleGroup（按维度：基本属性、社会属性、其他属性）
              └── 规则条件 RuleCondition（字段、操作符、期望值、权重、是否必填）
```

两个产品：
- 新加坡国际本硕升学计划
- 中德精英人才共建计划

规则条件支持：
- 硬性条件：必须满足，否则直接不符合。
- 评分条件：满足得分，按总分判断。
- 人工复核条件：如“动手能力强”“学习态度好”等主观项，可由规则给出待复核。

---

## 二、数据库设计

建议使用 MySQL，核心表如下。字段类型以 MySQL 为例。

### 1. 系统权限表

#### `sys_user` 用户表
| 字段          | 类型         | 说明        |
| ------------- | ------------ | ----------- |
| id            | bigint       | 主键        |
| username      | varchar(64)  | 登录名      |
| password_hash | varchar(255) | 密码哈希    |
| real_name     | varchar(64)  | 姓名        |
| phone         | varchar(20)  | 手机        |
| email         | varchar(128) | 邮箱        |
| status        | tinyint      | 1启用 0禁用 |
| dept_id       | bigint       | 部门        |
| last_login_at | datetime     | 最后登录    |
| created_at    | datetime     | 创建时间    |
| updated_at    | datetime     | 更新时间    |

#### `sys_role` 角色表
| 字段        | 类型         | 说明     |
| ----------- | ------------ | -------- |
| id          | bigint       | 主键     |
| role_code   | varchar(64)  | 角色编码 |
| role_name   | varchar(64)  | 角色名称 |
| description | varchar(255) | 描述     |
| status      | tinyint      | 状态     |
| created_at  | datetime     | 创建时间 |

#### `sys_permission` 权限表
| 字段      | 类型         | 说明                          |
| --------- | ------------ | ----------------------------- |
| id        | bigint       | 主键                          |
| perm_code | varchar(128) | 权限编码，如 `assessment:run` |
| perm_name | varchar(64)  | 权限名称                      |
| type      | varchar(16)  | menu/button/api               |
| parent_id | bigint       | 父级                          |
| path      | varchar(255) | 前端路由或API路径             |
| method    | varchar(16)  | GET/POST等                    |
| sort      | int          | 排序                          |

#### `sys_user_role` 用户角色关联
| 字段    | 类型   |
| ------- | ------ |
| user_id | bigint |
| role_id | bigint |

#### `sys_role_permission` 角色权限关联
| 字段          | 类型   |
| ------------- | ------ |
| role_id       | bigint |
| permission_id | bigint |

#### `sys_dict` 字典表
| 字段       | 类型         | 说明                         |
| ---------- | ------------ | ---------------------------- |
| id         | bigint       | 主键                         |
| dict_type  | varchar(64)  | 字典类型，如 education_level |
| dict_code  | varchar(64)  | 编码                         |
| dict_label | varchar(128) | 显示值                       |
| sort       | int          | 排序                         |
| status     | tinyint      | 状态                         |

#### `operation_log` 操作日志
| 字段          | 类型         | 说明     |
| ------------- | ------------ | -------- |
| id            | bigint       | 主键     |
| user_id       | bigint       | 操作人   |
| module        | varchar(64)  | 模块     |
| action        | varchar(64)  | 动作     |
| method        | varchar(16)  | 请求方法 |
| request_uri   | varchar(255) | 请求地址 |
| request_param | text         | 请求参数 |
| response_code | int          | 响应码   |
| ip            | varchar(64)  | IP       |
| created_at    | datetime     | 时间     |

---

### 2. 产品与规则表

#### `sys_product` 产品表
| 字段                    | 类型         | 说明                                 |
| ----------------------- | ------------ | ------------------------------------ |
| id                      | bigint       | 主键                                 |
| product_code            | varchar(64)  | 产品编码                             |
| product_name            | varchar(128) | 产品名称，如“新加坡国际本硕升学计划” |
| description             | text         | 描述                                 |
| status                  | tinyint      | 状态                                 |
| current_rule_version_id | bigint       | 当前发布规则版本                     |
| created_at              | datetime     | 创建时间                             |
| updated_at              | datetime     | 更新时间                             |

#### `sys_rule_version` 规则版本表
| 字段         | 类型         | 说明                    |
| ------------ | ------------ | ----------------------- |
| id           | bigint       | 主键                    |
| product_id   | bigint       | 产品ID                  |
| version_no   | varchar(32)  | 版本号                  |
| version_name | varchar(128) | 版本名称                |
| status       | varchar(16)  | draft/published/offline |
| effective_at | datetime     | 生效时间                |
| published_by | bigint       | 发布人                  |
| published_at | datetime     | 发布时间                |
| remark       | varchar(255) | 备注                    |
| created_at   | datetime     | 创建时间                |

#### `sys_rule_group` 规则组表
| 字段            | 类型          | 说明                             |
| --------------- | ------------- | -------------------------------- |
| id              | bigint        | 主键                             |
| rule_version_id | bigint        | 规则版本                         |
| group_code      | varchar(64)   | 组编码                           |
| group_name      | varchar(128)  | 组名称                           |
| dimension       | varchar(64)   | 维度：基本属性/社会属性/其他属性 |
| logic_type      | varchar(8)    | AND/OR                           |
| is_required     | tinyint       | 是否硬性组                       |
| weight          | decimal(10,2) | 组权重                           |
| sort            | int           | 排序                             |

#### `sys_rule_condition` 规则条件表
| 字段           | 类型          | 说明                                                  |
| -------------- | ------------- | ----------------------------------------------------- |
| id             | bigint        | 主键                                                  |
| rule_group_id  | bigint        | 规则组                                                |
| field_code     | varchar(64)   | 客户字段编码，如 age、education_level                 |
| operator       | varchar(32)   | EQ/NEQ/GT/GTE/LT/LTE/IN/CONTAINS/BETWEEN/REGEX/EXISTS |
| expected_value | json          | 期望值，如 `[14,16]`、`["初中","高中"]`               |
| value_type     | varchar(16)   | number/string/enum/json                               |
| weight         | decimal(10,2) | 分值                                                  |
| is_required    | tinyint       | 是否硬性条件                                          |
| error_msg      | varchar(255)  | 不满足提示                                            |
| sort           | int           | 排序                                                  |

#### `sys_field_dict` 客户字段字典
| 字段        | 类型         | 说明                            |
| ----------- | ------------ | ------------------------------- |
| id          | bigint       | 主键                            |
| field_code  | varchar(64)  | 字段编码                        |
| field_name  | varchar(128) | 字段名称                        |
| data_type   | varchar(16)  | string/number/boolean/date/enum |
| enum_values | json         | 枚举值                          |
| unit        | varchar(16)  | 单位                            |
| source_type | varchar(16)  | manual/parse/both               |
| is_query    | tinyint      | 是否可查询                      |
| sort        | int          | 排序                            |

---

### 3. 客户与文件表

#### `customer` 客户主表
| 字段           | 类型         | 说明               |
| -------------- | ------------ | ------------------ |
| id             | bigint       | 主键               |
| customer_no    | varchar(64)  | 客户编号           |
| name           | varchar(64)  | 姓名               |
| gender         | varchar(8)   | 性别               |
| birth_date     | date         | 出生日期           |
| age            | int          | 年龄               |
| phone          | varchar(20)  | 手机               |
| email          | varchar(128) | 邮箱               |
| id_card        | varchar(64)  | 身份证号，加密存储 |
| province       | varchar(64)  | 省                 |
| city           | varchar(64)  | 市                 |
| address        | varchar(255) | 地址               |
| source_channel | varchar(64)  | 来源渠道           |
| owner_user_id  | bigint       | 归属顾问           |
| status         | varchar(16)  | 状态               |
| created_at     | datetime     | 创建时间           |
| updated_at     | datetime     | 更新时间           |

#### `customer_profile_field` 客户画像字段表
采用“一行一字段”方式，方便规则引擎按 `field_code` 取值，也方便扩展。
| 字段           | 类型         | 说明                      |
| -------------- | ------------ | ------------------------- |
| id             | bigint       | 主键                      |
| customer_id    | bigint       | 客户ID                    |
| field_code     | varchar(64)  | 字段编码                  |
| field_value    | text         | 字段值                    |
| value_type     | varchar(16)  | 值类型                    |
| confidence     | decimal(5,2) | 抽取置信度                |
| extract_source | varchar(32)  | manual/pdf/excel/text/llm |
| created_at     | datetime     | 创建时间                  |
| updated_at     | datetime     | 更新时间                  |

可抽取字段示例：
- 年龄：`age`
- 学历：`education_level`
- 学校类型：`school_type`
- 毕业状态：`graduation_status`
- 专业：`major`
- 家庭年收入：`family_income`
- 留学预算：`study_budget`
- 目标国家：`target_country`
- 目标学历：`target_degree`
- 英语水平：`language_en_level`
- 德语水平：`language_de_level`
- 就业意向：`employment_intent`
- 移民意向：`immigration_intent`
- 动手能力：`hands_on_score`
- 逻辑思维：`logic_score`
- 学习态度：`learning_attitude_score`
- 政策关注度：`policy_attention`
- 留学意愿：`study_abroad_intent`

#### `customer_file` 客户文件表
| 字段           | 类型         | 说明                    |
| -------------- | ------------ | ----------------------- |
| id             | bigint       | 主键                    |
| customer_id    | bigint       | 客户ID                  |
| file_name      | varchar(255) | 文件名                  |
| file_type      | varchar(16)  | pdf/excel/text          |
| file_size      | bigint       | 文件大小                |
| file_path      | varchar(512) | 存储路径                |
| upload_user_id | bigint       | 上传人                  |
| parse_status   | varchar(16)  | 待解析/解析中/成功/失败 |
| created_at     | datetime     | 上传时间                |

#### `customer_file_parse` 文件解析记录表
| 字段            | 类型         | 说明               |
| --------------- | ------------ | ------------------ |
| id              | bigint       | 主键               |
| file_id         | bigint       | 文件ID             |
| parse_type      | varchar(16)  | pdf/excel/text/ocr |
| raw_text        | longtext     | 原始文本           |
| structured_json | json         | 结构化结果         |
| parse_status    | varchar(16)  | 状态               |
| error_msg       | varchar(512) | 错误信息           |
| created_at      | datetime     | 创建时间           |

---

### 4. 研判结果表

#### `assessment_task` 研判任务表
| 字段            | 类型        | 说明                    |
| --------------- | ----------- | ----------------------- |
| id              | bigint      | 主键                    |
| task_no         | varchar(64) | 任务编号                |
| customer_id     | bigint      | 客户ID                  |
| product_id      | bigint      | 产品ID                  |
| rule_version_id | bigint      | 使用的规则版本          |
| run_type        | varchar(16) | single/batch            |
| status          | varchar(16) | 待执行/执行中/成功/失败 |
| created_by      | bigint      | 创建人                  |
| started_at      | datetime    | 开始时间                |
| finished_at     | datetime    | 结束时间                |
| created_at      | datetime    | 创建时间                |

#### `assessment_result` 研判结果表
| 字段            | 类型          | 说明               |
| --------------- | ------------- | ------------------ |
| id              | bigint        | 主键               |
| task_id         | bigint        | 任务ID             |
| customer_id     | bigint        | 客户ID             |
| product_id      | bigint        | 产品ID             |
| rule_version_id | bigint        | 规则版本           |
| result          | varchar(16)   | pass/reject/review |
| total_score     | decimal(10,2) | 总分               |
| max_score       | decimal(10,2) | 满分               |
| pass_score      | decimal(10,2) | 通过分数线         |
| required_hit    | int           | 硬性命中数         |
| required_miss   | int           | 硬性未命中数       |
| summary         | varchar(512)  | 结论摘要           |
| created_at      | datetime      | 创建时间           |

#### `assessment_detail` 研判明细表
| 字段              | 类型          | 说明     |
| ----------------- | ------------- | -------- |
| id                | bigint        | 主键     |
| result_id         | bigint        | 结果ID   |
| rule_group_id     | bigint        | 规则组   |
| rule_condition_id | bigint        | 规则条件 |
| field_code        | varchar(64)   | 字段编码 |
| field_name        | varchar(128)  | 字段名称 |
| actual_value      | text          | 实际值   |
| operator          | varchar(32)   | 操作符   |
| expected_value    | text          | 期望值   |
| hit               | tinyint       | 是否命中 |
| score             | decimal(10,2) | 得分     |
| reason            | varchar(512)  | 原因     |
| created_at        | datetime      | 创建时间 |

#### `assessment_review` 人工复核表
| 字段           | 类型         | 说明          |
| -------------- | ------------ | ------------- |
| id             | bigint       | 主键          |
| result_id      | bigint       | 结果ID        |
| review_status  | varchar(16)  | 待复核/已复核 |
| review_user_id | bigint       | 复核人        |
| review_remark  | varchar(512) | 复核意见      |
| final_result   | varchar(16)  | 最终结论      |
| reviewed_at    | datetime     | 复核时间      |

---

## 三、角色与权限设计

### 1. 角色划分
| 角色           | 职责                                         |
| -------------- | -------------------------------------------- |
| 超级管理员     | 系统全部权限                                 |
| 产品规则管理员 | 维护产品、规则版本、规则条件、字段字典       |
| 研判操作员     | 录入/上传客户信息、发起研判、查看结果        |
| 审核员         | 对“待复核”结果进行人工复核                   |
| 数据分析员     | 查看统计报表、导出数据，只读                 |
| 外部API调用方  | 通过开放接口上传客户信息、发起研判、获取结果 |

### 2. 权限矩阵
| 权限项             | 超级管理员 | 产品规则管理员 | 研判操作员 | 审核员 | 数据分析员 | API调用方 |
| ------------------ | ---------- | -------------- | ---------- | ------ | ---------- | --------- |
| 用户/角色/权限管理 | ✅          | ❌              | ❌          | ❌      | ❌          | ❌         |
| 产品管理           | ✅          | ✅              | 只读       | 只读   | 只读       | ❌         |
| 规则版本/规则条件  | ✅          | ✅              | 只读       | 只读   | 只读       | ❌         |
| 字段字典           | ✅          | ✅              | 只读       | 只读   | 只读       | ❌         |
| 客户录入/编辑      | ✅          | ❌              | ✅          | ❌      | 只读       | ✅         |
| 文件上传/解析      | ✅          | ❌              | ✅          | ❌      | 只读       | ✅         |
| 发起研判           | ✅          | ❌              | ✅          | ❌      | ❌          | ✅         |
| 查看研判结果       | ✅          | ✅              | ✅          | ✅      | ✅          | ✅         |
| 人工复核           | ✅          | ❌              | ❌          | ✅      | ❌          | ❌         |
| 统计报表/导出      | ✅          | ✅              | ✅          | ✅      | ✅          | ❌         |
| 操作日志           | ✅          | ❌              | ❌          | ❌      | ❌          | ❌         |

### 3. 数据权限
- 研判操作员：只能查看自己创建或归属的客户。
- 审核员：可查看所有“待复核”和已复核结果。
- 产品规则管理员：可查看所有研判结果，但不能修改客户数据。
- 数据分析员：只读，不可修改任何业务数据。
- API调用方：只能访问自己提交的任务结果。

---

## 四、接口划分

建议 RESTful 风格，统一前缀 `/api/v1`。

### 1. 认证接口
| 方法 | 路径            | 说明         |
| ---- | --------------- | ------------ |
| POST | `/auth/login`   | 登录         |
| POST | `/auth/logout`  | 登出         |
| POST | `/auth/refresh` | 刷新Token    |
| GET  | `/auth/me`      | 当前用户信息 |

### 2. 系统管理接口
| 方法                | 路径                  | 说明     |
| ------------------- | --------------------- | -------- |
| GET/POST/PUT/DELETE | `/system/users`       | 用户管理 |
| GET/POST/PUT/DELETE | `/system/roles`       | 角色管理 |
| GET/POST/PUT/DELETE | `/system/permissions` | 权限管理 |
| GET/POST/PUT/DELETE | `/system/dicts`       | 字典管理 |
| GET                 | `/system/logs`        | 操作日志 |

### 3. 产品与规则接口
| 方法                | 路径                          | 说明         |
| ------------------- | ----------------------------- | ------------ |
| GET/POST/PUT/DELETE | `/products`                   | 产品管理     |
| GET/POST/PUT/DELETE | `/rule-versions`              | 规则版本管理 |
| POST                | `/rule-versions/{id}/publish` | 发布规则版本 |
| POST                | `/rule-versions/{id}/copy`    | 复制版本     |
| GET/POST/PUT/DELETE | `/rule-groups`                | 规则组管理   |
| GET/POST/PUT/DELETE | `/rule-conditions`            | 规则条件管理 |
| POST                | `/rules/test`                 | 规则测试     |
| GET/POST/PUT/DELETE | `/field-dicts`                | 字段字典管理 |

### 4. 文件与客户接口
| 方法                | 路径                      | 说明               |
| ------------------- | ------------------------- | ------------------ |
| POST                | `/files/upload`           | 上传文本/PDF/Excel |
| POST                | `/files/{id}/parse`       | 解析文件           |
| GET                 | `/files/{id}/preview`     | 预览解析结果       |
| GET/POST/PUT/DELETE | `/customers`              | 客户管理           |
| POST                | `/customers/import`       | 批量导入           |
| GET                 | `/customers/{id}/profile` | 查看客户画像       |
| PUT                 | `/customers/{id}/profile` | 人工补录画像字段   |

### 5. 研判接口
| 方法 | 路径                        | 说明         |
| ---- | --------------------------- | ------------ |
| POST | `/assessments/run`          | 单客户研判   |
| POST | `/assessments/batch-run`    | 批量研判     |
| GET  | `/assessments/{id}`         | 查看研判结果 |
| GET  | `/assessments/{id}/details` | 查看命中明细 |
| POST | `/assessments/{id}/review`  | 人工复核     |
| GET  | `/assessments/export`       | 导出结果     |

### 6. 统计接口
| 方法 | 路径              | 说明       |
| ---- | ----------------- | ---------- |
| GET  | `/stats/overview` | 总览统计   |
| GET  | `/stats/product`  | 按产品统计 |
| GET  | `/stats/channel`  | 按渠道统计 |

### 7. 开放API
| 方法 | 路径                               | 说明                       |
| ---- | ---------------------------------- | -------------------------- |
| POST | `/openapi/v1/assessments`          | 外部系统提交客户信息并研判 |
| GET  | `/openapi/v1/assessments/{taskNo}` | 查询研判结果               |

---

## 五、目录架构设计

### 1. 后端目录（以 Spring Boot 为例）
```text
src/main/java/com/company/profile/
├── ProfileApplication.java
├── common/
│   ├── result/                 # 统一返回
│   ├── exception/              # 全局异常
│   ├── enums/                  # 枚举
│   └── util/                   # 工具类
├── config/
│   ├── SecurityConfig.java
│   ├── SwaggerConfig.java
│   └── MybatisConfig.java
├── controller/
│   ├── AuthController.java
│   ├── CustomerController.java
│   ├── FileController.java
│   ├── AssessmentController.java
│   ├── RuleController.java
│   ├── ProductController.java
│   └── StatsController.java
├── service/
│   ├── AuthService.java
│   ├── CustomerService.java
│   ├── FileParseService.java
│   ├── AssessmentService.java
│   ├── RuleService.java
│   ├── ProductService.java
│   └── impl/
├── domain/
│   ├── entity/                 # 数据库实体
│   ├── dto/                    # 入参
│   ├── vo/                     # 出参
│   └── query/                  # 查询条件
├── repository/
│   └── mapper/                 # MyBatis Mapper
├── rule/
│   ├── RuleEngine.java         # 规则引擎入口
│   ├── RuleContext.java        # 规则上下文
│   ├── operator/               # 操作符实现
│   ├── evaluator/              # 条件评估器
│   └── score/                  # 评分计算
├── parser/
│   ├── FileParser.java         # 解析接口
│   ├── PdfParser.java
│   ├── ExcelParser.java
│   ├── TextParser.java
│   └── ProfileExtractor.java   # 字段抽取
├── security/
│   ├── JwtFilter.java
│   └── UserDetailsServiceImpl.java
└── job/
    └── AssessmentBatchJob.java
```

```text
src/main/resources/
├── application.yml
├── mapper/                     # XML映射
└── db/migration/               # Flyway/Liquibase脚本
```

### 2. 前端目录（以 Vue3 为例）
```text
src/
├── api/                        # 接口封装
├── views/
│   ├── customer/               # 客户管理
│   ├── assessment/             # 研判结果
│   ├── rule/                   # 规则配置
│   ├── product/                # 产品管理
│   └── system/                 # 系统管理
├── components/                 # 公共组件
├── router/                     # 路由
├── store/                      # 状态管理
└── utils/                      # 工具
```

---

## 六、研判流程与规则引擎

### 1. 研判流程
1. 录入或上传客户信息。
2. 文件解析：PDF 用 PDFBox，Excel 用 EasyExcel，文本直接读取。
3. 字段抽取：正则 + 关键词 + 可选 LLM，映射到 `customer_profile_field`。
4. 加载产品当前已发布规则版本。
5. 规则引擎执行：
   - 先判断硬性条件：全部满足才进入评分。
   - 再计算评分条件：按权重累加。
   - 总分 >= 通过分数线 → `pass`。
   - 硬性不满足 → `reject`。
   - 主观项或置信度低 → `review`。
6. 保存研判结果和明细。
7. 审核员可对 `review` 结果人工复核。

### 2. 规则条件示例
新加坡项目：
- 年龄 BETWEEN [14,16] 或 [16,19]
- 学历 IN [初中, 高中, 中职, 中技]
- 留学意愿 CONTAINS 新加坡
- 预算 GTE 25万

中德项目：
- 年龄 BETWEEN [18,35]
- 学历 GTE 高中
- 德语水平 GTE B1 或 有德语学习潜力
- 移民意向 EXISTS
- 动手能力/逻辑思维/学习态度 评分项

### 3. 结果判定建议
| 情况                                 | 结果       |
| ------------------------------------ | ---------- |
| 硬性条件全部满足，总分 ≥ 阈值        | 符合       |
| 硬性条件未满足                       | 不符合     |
| 硬性满足但总分接近阈值，或主观项缺失 | 待复核     |
| 文件解析失败或关键字段缺失           | 待补充信息 |

---

## 七、技术选型与实施建议

- 后端：Spring Boot + MyBatis-Plus + MySQL + Redis
- 文件存储：MinIO 或本地文件系统
- PDF解析：Apache PDFBox
- Excel解析：EasyExcel
- 安全：Spring Security + JWT + API Key
- 规则引擎：轻量自研即可，复杂可引入 Drools
- 字段抽取：正则 + 关键词 + 可选大模型辅助
- 前端：Vue3 + Element Plus
- 数据库版本管理：Flyway
- 日志与审计：操作日志、研判明细全留痕

### MVP 最小落地表
优先建：
`sys_user`、`sys_role`、`sys_permission`、`sys_user_role`、`sys_role_permission`、`sys_product`、`sys_rule_version`、`sys_rule_group`、`sys_rule_condition`、`sys_field_dict`、`customer`、`customer_profile_field`、`customer_file`、`customer_file_parse`、`assessment_task`、`assessment_result`、`assessment_detail`、`assessment_review`。

这样既能满足两个产品的研判，又方便后续新增产品、调整规则和人工复核。