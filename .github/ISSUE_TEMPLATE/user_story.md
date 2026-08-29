---
name: User Story
about: 用 INVEST + 3C + Gherkin 模板提交一个用户故事需求
title: "[US] 简短的用户故事标题"
labels: [user-story]
assignees: ''
---

## 用户故事 (Card)
**作为** _<角色, 如:玩家/主持人/管理员>_
**我想要** _<能力, 如:在回合中输入自由行动并得到 DM 实时判决>_
**以便** _<价值, 如:获得沉浸式跑团体验>_

## 验收标准 (Confirmation / Acceptance Criteria)
- [ ] Gherkin Given/When/Then 场景 1:...
- [ ] Given/When/Then 场景 2:...
- [ ] 数值判定(Pydantic 结构化检定)返回正确的 skill/dc/total/success 字段
- [ ] 输入校验与提示词防护拦截非法输入(422/不泄露提示词)

## 会话要点 (Conversation)
- 前置条件:PRE-xxx
- 后置条件:POST-xxx
- 依赖的模块:LLM Provider / Dice Roller / Persistence / Frontend

## Story Points
- [ ] 1 (S)  [ ] 2 (M)  [ ] 3 (L)  [ ] 5 (XL)

## 关联
- 关联 Sprint:S1 / S2 / S3 / S4
<br/>
## 测试链接
- 单元测试:`tests/unit/...`
- BDD 验收:`tests/bdd/features/...`