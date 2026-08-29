# Sprint 4 迭代报告 — CI/CD 流水线、开源发布与复盘

> 周期:Sprint 4 · 里程碑:GitHub Actions CI 准入 + Docker 容器化 + 开源发布就绪
> 看板流转:To Do → In Progress → In Review → Done

## 1. Sprint 目标

- GitHub Actions CI:ruff lint → pytest(覆盖率)→ behave BDD → eval 轨迹四道门禁
- Docker 容器化:Dockerfile + docker-compose(前后端一体 + 数据库卷)
- 开源发布就绪:README 工业级主文档、License、Badge、Demo 视频说明、贡献指引
- 复盘与人机协同过程沉淀:AGENTS.md / .rules、GitHub 规范(Commit/PR 模板/Issue 模板)

## 2. Backlog 完成情况

| # | Backlog 项 | SP | 流转 | 完成 | 验证 |
|---|---|---|---|---|---|
| S4-01 | .github/workflows/ci.yml(lint→test→bdd→eval→docker) | 3 | To Do→Done | 是 | PR 门禁模拟 |
| S4-02 | Issue 模板(User Story/Bug/Feature) | 1 | To Do→Done | 是 | 模板渲染 |
| S4-03 | PULL_REQUEST_TEMPLATE.md | 1 | To Do→Done | 是 | 评审清单对齐 |
| S4-04 | Dockerfile + docker-compose.yml | 2 | To Do→Done | 是 | build 冒烟 |
| S4-05 | README 工业级主文档(Badges/架构/快速启动/贡献) | 2 | To Do→Done | 是 | 文档评审 |
| S4-06 | AGENTS.md / .rules 项目规则 | 1 | To Do→Done | 是 | 规则对齐 |
| S4-07 | pyproject.toml(ruff/pytest 卡点固化) | 1 | To Do→Done | 是 | CI 等价 |
| S4-08 | 覆盖率提升与全量回归 | 2 | To Do→Done | 是 | ≥80% 达标 |

## 3. 关键技术决策

1. **CI 五段式门禁**:`lint → test → bdd → eval → docker-build` 串行依赖,仅全绿可合并(与主分支保护策略一致)。
2. **Docker 一次性镜像**:requirements 先 COPY 再 COPY 代码,利用层缓存;HEALTHCHECK 探活 `/api/health`;`docker-compose` 注入全部环境变量(默认 mock,一键可跑)。
3. **评审清单即模板**:PR 模板内嵌防御性编程自查 + CI 绿灯 + 敏感信息不入库,降低审查遗漏。
4. **规则注入**:AGENTS.md / .rules 声明“分层解耦、Provider 抽象、结构化契约、禁止越层直连”,供 AI/人共同遵守。

## 4. Demo

最终演示视频(README 中链接):启动 `docker compose up` → 浏览器开篇 → 自由行动流式叙述 → `/check` 数值裁决 → 分支树推进 → `/restart`。CI 全绿:ruff 0 error / pytest 59 + BDD 6 绿 / eval 100%。

## 5. 质量基线(发布前)

- ruff check app tests eval:0 error
- pytest:59 passed;behave:6 scenarios passed
- eval/score.py 轨迹通过率 100%
- Docker build 冒烟通过

## 6. 风险与整改

| 风险 | 处置 |
|---|---|
| 真实 API 依赖不稳定 | 全链路 mock 保底;CI 全程离线可跑 |
| 覆盖率高但漏场景 | BDD + eval 双轨补位,回归在 CI 固化为证据 |
| 协作规范形同虚设 | 模板与门禁制度化,PR 未过 CI 禁止合并 |

## 7. 最终复盘

- **达到**:MVP→多模态→体验/防御/评测→CI/CD 发布的完整工程闭环;程序在 mock 下全程可运行,具备真实 DeepSeek/硅基流动接入能力。
- **经验**:①“数值裁决归引擎、叙事归 LLM”的分层让系统稳定可测;②防御性编程必须落在边界(输入/守卫/频控/异常/脱敏)而非堆 try；③EDD 让跑团质量可回归、可发布。
- **后续**:接入真实 Key 做线上验收;分支树升级为 Mermaid 渲染;引入 Redis 频控与异步消息队列。

## 8. 贡献清单

- CI/CD、Docker、模板、AGENTS:全组协作
- README 与发布文档:A、C
- 复盘与规则沉淀:B、D
- 最终 Demo 演示:全组