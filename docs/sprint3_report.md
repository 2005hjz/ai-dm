# Sprint 3 迭代报告 — 交互体验、防御性编程与 EDD 评测

> 周期:Sprint 3 · 里程碑:剧情分支树可视化 + 防御性编程 + 轨迹评测(EDD)
> 看板流转:To Do → In Progress → In Review → Done

## 1. Sprint 目标

- 剧情分支树可视化:`/api/scenario/branches` + 前端面板高亮当前场景
- 防御性编程:全局异常处理/输入校验/提示词防护/滑动窗口频控/日志脱敏
- EDD(证据驱动开发):`eval/evalset.json` 轨迹评测 + 评分脚本
- 交互体验:SSE 打字机效果、侧栏实时刷新、错误提示不崩溃

## 2. Backlog 完成情况

| # | Backlog 项 | SP | 流转 | 完成 | 验证 |
|---|---|---|---|---|---|
| S3-01 | /api/scenario/branches 端点 | 2 | To Do→Done | 是 | test_scenario_branches |
| S3-02 | 前端分支树面板渲染+当前场景高亮 | 3 | To Do→Done | 是 | 前端手测 |
| S3-03 | 全局异常处理中间件(500→结构化 JSON) | 2 | To Do→Done | 是 | 防御性单测 |
| S3-04 | 提示词防护 scan_guardrails | 2 | To Do→Done | 是 | test_safety / BDD |
| S3-05 | 滑动窗口频控(429) | 2 | To Do→Done | 是 | test_rate_limit |
| S3-06 | 日志脱敏 guard_log | 1 | To Do→Done | 是 | 单测 |
| S3-07 | eval/evalset.json + eval/score.py | 3 | To Do→Done | 是 | 通过率 100% |
| S3-08 | BDD 验收(守卫/推进/拒绝) | 2 | To Do→Done | 是 | behave 全绿 |

## 3. 关键技术决策

1. **EDD 证据驱动**:`eval/score.py` 用固定 seed 回放 7 条轨迹,逐断言评分,产出 `report.txt/report.json`——把“跑团质量”变成可回归的证据。
2. **守卫不硬拒、角色内化解**:越狱命中后返回“雾里的低语”并跳过 LLM,避免提示词泄露,也避免打断游戏沉浸。
3. **频控放中间件而不散落业务**:滑动窗口按客户端 IP,对 `/api/*` 生效,超限 429,可注入测试。
4. **分支树双源**:业务推进规则(`scene_chain`/`advance_on`/`scene_shortcut`)与可视化端点同一数据源,避免模型漂移。

## 4. Demo

右侧新增「剧情分支树」面板:prologue→hallway→room7→basement→end 链路 + 直达捷径,当前场景金色高亮;输入「我推开7号房的门」瞬间推进并高亮 room7;`eval/score.py` 输出 7/7 轨迹 PASS。

## 5. 质量基线

- ruff 全量通过(app/tests/eval 0 错误)
- pytest 59 用例 + behave 6 场景全绿;覆盖率 80%(target Sprint 4 ≥85%)
- 轨迹评测通过率 100%

## 6. 风险与整改

| 风险 | 处置 |
|---|---|
| 频控误伤正常玩家 | 默认限 60 req/min,配置可调;测试可注入宽松限流 |
| 守卫误拦截正向意图 | 守卫仅命中注入/越狱模式,常规行动语句不受影响(已用 BDD 断言) |
| 遥测写入失败 | try/except 吞噬并 warn,不回传影响主流程 |

## 7. 复盘

- **好**:防御性编程真正落到边界(输入→守卫→频控→异常→脱敏);EDD 让每次发布都可证质量。
- **待改**:覆盖率仍 80%,目标 85%+;CI 全量门禁在 Sprint 4 接通。

## 8. 贡献

- 分支树端点与前端面板:B、C
- 防御性编程层(守卫/频控/异常/脱敏):A、B
- EDD 评测集与评分脚本:A、D
- BDD 用例化:C、全组评审

**遗留**:sprint1_report 由小组补齐后经 PR 入主分支(质量门禁:CI 绿灯 + 1 名成员 Review)。