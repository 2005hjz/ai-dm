# AGENTS.md — 项目规则与 AI 协作注入规范

> 本文档是本仓库的“宪法”,供人类成员与 AI 编程助手共同遵守。任何 PR 违反下文约束,评审应拒绝合并。

## 1. 架构约束(高内聚、分层解耦)

- 分层: `presentation(main.py/static) → application(gameplay.py/providers.py) → domain(models.py/scenario.py) → infrastructure(persistence.py/storage.py/config.py)`。
- **禁止**跨层越级直连(如 route 里直接写 SQLite);一律经由 `storage`/`persistence` 门面。
- 业务规则(骰子/检定/剧情)放在 `domain` 层,不依赖具体 LLM。

## 2. 核心模式

- **Provider 抽象**:LLM 与生图只通过 `BaseLLMProvider`/`BaseImageProvider` 接口调用;新增供应商 = 新增子类 + 改 `.env`,不改业务代码。
- **结构化数值契约**:一切检定结果使用 Pydantic(`DiceRoll`/`CheckResult`/`DMPlan`/`SkillProposal`),禁止裸 dict 传递。
- **防御性编程**:任何外部调用(LLM/生图)成功后才有数据;失败一律 `try/except` 降级 mock,主流程永不中断。
- **双轨持久化**:会话正文 JSON;结构化审计/度量 SQLite。

## 3. 安全红线

- 真实 API Key **严禁**入库;只允许 `.env.example` 模板。
- 输入先过 `safety.sanitize_input`,再过 `safety.scan_guardrails`;命中注入就地化解。
- 日志脱敏:经 `safety.guard_log` 后才可打印。
- 提示词(系统提示词模板)默认视为机密,不得回显给用户。

## 4. 编码规范

- Python ≥3.10,`from __future__ import annotations` 优先。
- 不写无注释装饰性注释;代码即文档,必要处给类型标注。
- 行宽 120,ruf 规则见 `pyproject.toml`(`ruff check app tests eval` 必须 0 error)。
- 测试新增必配断言(确定性 seed: `roll_expression(expr, seed=42)`)。

## 5. Git / PR 规范

- Commit 使用 Angular 约定:`feat/fix/test/docs/refactor/chore: 说明`。
- 严禁直接 push 主分支;一律 PR,至少 1 名成员 Review,等 CI 绿灯后合并。
- Issue 使用仓库模板(User Story / Bug / Feature),标注 Story Points。

## 6. 验证门禁(发布/合并前必跑)

```bash
ruff check app tests eval
python -m pytest tests -q
behave tests/bdd/features
python eval/score.py
```
任一门禁失败 → PR 不得合并。