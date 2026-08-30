# 看板 — 基于当前完成程度的待填写清单

> 用途:按当前工程完成状态(Sprint 1–4 已交付),拆分为四个看板列。每张卡片留「文本内容」占位,供填写:任务说明 / 完成度 / 责任人 / 验证口径。

## 看板列一:To Do(待办)

| # | 卡片(文本内容待填) | 备注 |
|---|---|---|
| TD-01 | 真实 Key 线上验收:启用 deepseek + 生图 Key 跑完整一局 | 已完成 Key 实测,需补演示记录 |
| TD-02 | 分支树升级为 Mermaid 可视化渲染 | Sprint 4 遗留规划 |
| TD-03 | Redis 频控 + 异步消息队列改造 | Sprint 4 后续规划 |
| TD-04 | 覆盖率 ≥85% 目标回归核验 | 当前 80%+,未最终确认 |

## 看板列二:In Progress(进行中)

| # | 卡片(文本内容待填) | 备注 |
|---|---|---|
| IP-01 | ⌈新 Key 生图验证⌉ 生成图片已成功(617KB PNG) | 待补 Demo 截图与记录 |
| IP-02 | ⌈演示视频⌉ 全链路 Demo 录制(Docker 起服务→对话→检定→生图) | README 已留演示链接占位 |

## 看板列三:In Review(评审中)

| # | 卡片(文本内容待填) | 备注 |
|---|---|---|
| IR-01 | ⌈Sprint 1 报告⌉ 需求规约与 MVP 骨架 | 需小组补齐后入 PR |
| IR-02 | ⌈贡献清单⌉ 各成员分工与评审记录 | 全组待补名 |
| IR-03 | ⌈安全红线核对⌉ 真实 Key 不入库、日志脱敏 | 需 PR 评审核对 |

## 看板列四:Done(已完成)

| # | 卡片(文本内容待填) | 验证口径 |
|---|---|---|
| D-01 | 仓库拓扑 + .env/requirements/.gitignore | 结构核对 |
| D-02 | Pydantic 结构化契约(DiceRoll/CheckResult/DMPlan/SkillProposal) | 单测通过 |
| D-03 | 骰子表达式解析与 seeded 检定 | test_dice 全绿 |
| D-04 | 技能检定数值裁决 + dc_override | test_gameplay / test_providers |
| D-05 | JSON 会话持久化 + SQLite 遥测双轨 | 重启冒烟 / test_storage |
| D-06 | FastAPI REST 路由 + 前端交互(SSE 流式) | API 流测 / 前端手测 |
| D-07 | 斜杠指令全套(`/roll` `/check` `/restart` 等) | BDD 通过 |
| D-08 | Provider 抽象:LLM 与生图远端接入 + mock 自动降级 | 链路单测,生图 Key 实测通过 |
| D-09 | 上下文记忆滑动窗口 + token 预算 | test_memory |
| D-10 | 分支树端点 + 前端高亮面板 | test_scenario_branches |
| D-11 | 防御性编程:全局异常/守卫/频控/日志脱敏 | test_safety / test_rate_limit / BDD |
| D-12 | EDD 评测(eval/score.py 轨迹 100%) | eval 通过率 100% |
| D-13 | CI 五段式门禁 + Docker 容器化 + 开源发布文档 | ruff 0 error / pytest 59 + BDD 6 / docker build |
| D-14 | AGENTS.md / .rules 协作规范注入 | 规则评审 |

## 填写模板(单卡片样式)

```markdown
### 卡片标题
- 目标:
- 完成度: 0/10 (待填)
- 责任人: (待填)
- 验证口径: (待填)
- 备注: (待填)
```