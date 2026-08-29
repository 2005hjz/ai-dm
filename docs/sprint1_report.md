# Sprint 1 迭代报告 — 需求规约与 MVP 骨架

> 周期:Sprint 1 · 里程碑:单场景文本跑团 + 基础骰子检定 + 会话持久化(MVP)
> 看板流转:To Do → In Progress → In Review → Done

## 1. Sprint 目标

- 单场景文本跑团:《雾中孤儿院》`prologue` 开场 + 玩家自由行动 + DM 叙述
- 基础骰子检定逻辑:`/roll`、`/check` 数值裁决(success / degree)
- 对话状态持久化:JSON 会话文件,服务重启可恢复
- 工程骨架:`.env.example`、`.gitignore`、`requirements(-dev).txt`、测试基线

## 2. Backlog 完成情况

| # | Backlog 项 | SP | 流转 | 完成 | 验证 |
|---|---|---|---|---|---|
| S1-01 | 仓库拓扑(git/.gitignore/requirements/.env.example) | 1 | To Do→Done | 是 | 结构核对 |
| S1-02 | Pydantic 数据契约(models.py) | 2 | To Do→Done | 是 | 单测通过 |
| S1-03 | 骰子表达式解析与投掷 | 2 | To Do→Done | 是 | test_dice 全绿 |
| S1-04 | 技能检定数值裁决 | 3 | To Do→Done | 是 | test_gameplay 全绿 |
| S1-05 | JSON 会话持久化与恢复 | 2 | To Do→Done | 是 | 重启冒烟 |
| S1-06 | FastAPI REST 路由 + 前端骨架 | 2 | To Do→Done | 是 | /api/health |
| S1-07 | 斜杠指令全套 | 2 | To Do→Done | 是 | BDD 通过 |

## 3. 关键技术决策

1. **双轨持久化**:会话正文 → JSON 文档;结构化数值审计 → SQLite(`check_log`/`session_metrics`)。
2. **确定性测试**:`roll_expression(expr, seed=...)` 支持 seed 注入,骰子检定可复现。
3. **Provider 抽象先行**:`BaseLLMProvider`/`BaseImageProvider` 接口 Sprint 1 定稿,`MockImageProvider` 本地 SVG 场景卡,保证离线可跑。

## 4. Demo

`uvicorn app.main:app --port 8000` → 新冒险 → 「我推开门」→ DM 叙述 → `/roll 1d20+3` → `/check 侦查` → 结构化检定;重启服务后会话可恢复。

## 5. 质量基线

- pytest 全绿;覆盖率基线与 Sprint 3 目标 ≥85%
- 安全基线:sanitize_input 拒绝空/超长输入(422)

## 6. 风险与整改

| 风险 | 处置 |
|---|---|
| 无真实 API Key | mock 保底,离线可跑 |
| 会话 JSON 随轮次膨胀 | Sprint 2 引入 memory 滑动窗口 + token 预算 |
| CI 未接通 | Sprint 4 交付 CI workflow;先本地 ruff+pytest 内建卡点 |

## 7. 复盘

- **好**:gameplay 不依赖具体 LLM,可独立测试;seed 让骰子可测。
- **待改**:config 硬编码 → Sprint 2 改为 dotenv 驱动;SSE 流式叙述 → Sprint 2;分支树 → Sprint 3。

## 8. 贡献

- 后端核心(启动/会话/dice/check/persistence):A、B
- 前端骨架与指令交互:C
- 测试基线:全组评审通过