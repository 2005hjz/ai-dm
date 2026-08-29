<!-- PR 审查标准模板:至少一名成员 Code Review 批准 + CI 绿灯后方可合并 -->
## 关联 Issue
- 关闭: #<issue-number>

## 变更摘要 (Summary)
- 模块:app/ · tests/ · static/ · docs/ · eval/ · .github/
- 一句话说明:

## 变更点 (Changes)
- [ ] 新增/修改的模块与文件:
- [ ] 依赖变化:requirements.txt / requirements-dev.txt
- [ ] 环境变量/配置变化:.env.example 是否同步?

## 测试与验证 (Testing)
- [ ] `python -m pytest tests -q` 全绿
- [ ] `behave tests/bdd/features` 全绿
- [ ] `python eval/score.py` 通过率
- [ ] 手动冒烟:mock 模式下创建会话 → /roll → /check → 自由行动推进场景

## 防御性编程自查
- [ ] 输入校验(长度/控制字符)已处理
- [ ] 提示词注入扫描已覆盖
- [ ] 频控/异常兜底不破坏主流程
- [ ] 真实 API Key 未入库(仅 .env.example)

## 评审清单 (Review Checklist)
- [ ] CI 绿灯 (lint / pytest / behave / eval)
- [ ] 代码风格与架构分层一致(高内聚,分层解耦)
- [ ] 无敏感信息泄露(密钥/日志脱敏)
- [ ] README/文档是否需同步更新

## 截图 / 演示(可选)