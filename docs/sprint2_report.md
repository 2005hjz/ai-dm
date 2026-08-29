# Sprint 2 迭代报告 — 核心业务逻辑与多模态接入

> 周期:Sprint 2 · 里程碑:真实 LLM/生图多模态接入 + 流式响应 + 上下文记忆管理
> 看板流转:To Do → In Progress → In Review → Done

## 1. Sprint 目标

- 多模态接入:DeepSeek/硅基流动 OpenAI 兼容 LLM Provider + 远程生图 Provider(mock 自动降级)
- SSE 流式叙述:前端逐 token 渲染,`done` 帧收尾
- 上下文记忆管理:滑动窗口 + token 预算截断(memory.py)
- `DMPlan` / `SkillProposal` 结构化契约:LLM 建议检定 → 引擎数值裁决

## 2. Backlog 完成情况

| # | Backlog 项 | SP | 流转 | 完成 | 验证 |
|---|---|---|---|---|---|
| S2-01 | dotenv 环境驱动配置 | 1 | To Do→Done | 是 | .env.example / config |
| S2-02 | DeepSeekLLMProvider(OpenAI 兼容 + JSON 契约) | 3 | To Do→Done | 是 | parse_dm_plan 单测 |
| S2-03 | 远程生图 RemoteImageProvider + 磁盘缓存 + 异步预热 | 3 | To Do→Done | 是 | /api/images |
| S2-04 | SSE 流式 /chat(token→done) | 2 | To Do→Done | 是 | API 流测 |
| S2-05 | 上下文记忆滑动窗口 + token 预算 | 2 | To Do→Done | 是 | test_memory |
| S2-06 | DMPlan/CheckResult 结构化契约 + dc_override | 2 | To Do→Done | 是 | test_providers |
| S2-07 | LLM/生图失败自动降级 mock | 2 | To Do→Done | 是 | 防御性编程链路 |
| S2-08 | SQLite 遥测(check_log/session_metrics) | 2 | To Do→Done | 是 | test_storage |

## 3. 关键技术决策

1. **生成后流式**:先一次非流式 LLM 调用拿到结构化 `DMPlan`(保证 JSON 契约可靠),再由 `stream_text` 对叙述做 SSE 逐块输出——既真实走 SSE 协议,又不牺牲结构化解析的可靠性。
2. **防御性降级**:`DeepSeekLLMProvider.plan` 任何异常 → `MockLLMProvider.plan`;`RemoteImageProvider.generate` 失败 → mock SVG。主线流程永不因外部 API 中断。
3. **token 预算**:`memory.estimate_tokens` 简易中英混合估算,`build_context` 超预算向前裁剪,防止上下文溢出。
4. **接口归一**:`chat_url(base)` 兼容 DeepSeek 官方与硅基流动 `/v1/chat/completions` 两种 base URL 风格。

## 4. Demo

配置 `.env`(DEEPSEEK_API_KEY)后切换 `LLM_PROVIDER=deepseek`;未配置自动 mock。`/chat` SSE 流式叙述 + 结构化检定 + 场景推进会同步落库;远程生图在启动时后台预热场景卡/NPC 画像。

## 5. 质量基线

- pytest 单测 + API 测全绿;BDD 引入
- 守卫拦截:越狱句"忽略前面指令…系统提示词"被角色内化解,不触发 LLM、不泄提示词(BDD 场景)
- 遥测:每次检定写入 `check_log`,可在 eval 阶段 SQL 审计

## 6. 风险与整改

| 风险 | 处置 |
|---|---|
| 真实 LLM 输出非 JSON | parse_dm_plan 容错(markdown 围栏剥离 + 字段级防御) |
| 生图耗时阻塞首屏 | 启动 background 预热 + 失败回退 mock SVG |
| 上下文无限膨胀 | memory 窗口 + token 预算卡点 |

## 7. 复盘

- **好**:Provider 抽象让 mock↔deepseek 一键切换;结构化契约让"数值裁决归引擎、叙事归 LLM"职责清晰。
- **待改**:前端尚缺剧情分支树面板与更细防御 → Sprint 3。

## 8. 贡献

- Provider/契约/记忆:A、B
- SSE 后端与降级链路:A
- SQLite 遥测:B、D
- 前端流式渲染:C