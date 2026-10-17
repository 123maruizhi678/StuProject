# 客户研判大模型测试报告

测试日期：2026-10-17（Asia/Shanghai）。目标代码：D:/code/StuProject。Dify：本机1.12.1。

## 已部署结果

独立应用“客户信息抽取”已更新并发布，ID：8658ad46-1bea-4a41-89d3-6312fc578dd8。
模型使用本地工作区现有 deepseek-flash；后端专用API地址为 http://127.0.0.1/v1。
工作流与后端双重校验v1版本和固定13字段，不允许模型输出研判结论、权限或归属。
实际应用Key已配置在目标项目本地.env，本报告不包含密钥。

## 验证结果

| 验证 | 结果 |
| --- | --- |
| SST目标环境：客户测试、公共响应、客服Dify客户端回归 | 61/61通过 |
| 客户模块专项单元测试 | 43/43通过 |
| 真实Dify合成样本和非法契约测试 | 12/12通过 |
| 合成样本预期字段逐值比对 | 41/41项一致，无多余字段 |
| SST目标环境再次调用完整样本 | 13/13字段正确，工作流成功 |
| 客户服务及API定义导入 | 成功，9个路由定义可加载 |

10条模型样本平均耗时1.95秒，范围1.58—2.36秒。
完整资料交给示例固定规则后命中、得分30；稀疏资料和零工龄资料不命中。数字阈值恰好相等时的重复计分缺陷已修复并回归。
非法版本、非法Schema均收到HTTP200但工作流status=failed，测试按预期识别为拒绝，未把HTTP200当成成功。

真实样本：完整13字段、叙述型资料、稀疏资料、不提供个人资料、提示注入、中文叙述与号码清理、不造产品编码、零工龄、多客户不混合、邮箱不推断姓名。
故障单元测试覆盖401/429/500、超时、无密钥、非法JSON、非法字段、错误类型、越界数字、版本不匹配及确定性回退；不自动重发模型请求。

逐项运行ID和耗时见 verification.json；SST复核见 target-runtime-verification.json。

## 交付边界

已交付DSL、后端严格契约/适配器/抽取服务、部署和复测脚本、必要导入修复、测试用例与依赖清单。
本次只使用合成数据，没有建表、写入业务表或修改前端文件。
原main.py尚未挂载客户业务路由，本次未进行来源入库、业务JWT/部门范围、批量事务、完整PDF/Excel入库或9接口端到端验收。完整模块上线仍需独立接通并验收这些业务部分。
样本结果不代表已达到真实业务资料95%准确率；正式画像规则和真实业务样本仍需业务确认。

## 复测命令

在 D:/code/StuProject 中使用 SST Python：

```powershell
python -m pytest tests/customer tests/common/test_response.py tests/agent/test_dify_client.py -q
python scripts/customer/verify_dify.py
```

工作流更新前图保存在本目录backups；代码原始备份位于 C:/Users/Windows/Documents/ChatGPT/StuProject/customer_backend_originals。
