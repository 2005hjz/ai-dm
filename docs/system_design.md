# 系统设计规约 — AI 赛博 DM 与无限跑团/剧本杀引擎

> 版本:v1.0  ·  对应 Sprint 1-4  ·  架构基线:分层解耦 + 三个系统模型(功能/数据/动态)共 6 张核心架构图
> 本文档为团队唯一架构权威(AD),所有模块与 PR 均须与此保持一致。

---

## 0. 架构原则(与 AGENTS.md / .rules 对齐)

1. **严格分层**:`api(表现层) → application(玩法/决策引擎) → domain(领域模型) → infrastructure(存储/外部 Provider)`。禁止跨层直连。
2. **Provider 抽象**:LLM 与生图全部走接口(`BaseLLMProvider` / `BaseImageProvider`),本地 `mock` 保底,接真实 API 只改配置不改代码。
3. **结构化数值契约**:所有骰子检定使用 Pydantic 模型(`DiceRoll` / `CheckResult` / `DMPlan`),模型输出解析失败自动降级 mock(防御性编程)。
4. **防御性编程**:输入校验 → 提示词防护 → 滑动窗口频控 → 全局异常处理 → 日志脱敏。
5. **持久化双轨**:会话正文用 JSON 文档(可版本化、易读),结构化数值审计用 SQLite(`check_log` / `session_metrics`)。
6. **记忆管理**:多轮对话滑动窗口 + token 预算截断(`memory.py`),防止上下文溢出。

---

## 一、功能模型 (Functional Model)

### 1.1 系统顶层用例图 (Use Case Diagram)

```mermaid
flowchart LR
    subgraph SystemBoundary["AI-DM 引擎"]
        UC1["创建/恢复会话"]
        UC2["自由行动(文本输入)"]
        UC3["/roll 掷骰指令"]
        UC4["/check 技能检定"]
        UC5["/scene 场景卡"]
        UC6["/hp 状态查看"]
        UC7["/restart 重置"]
        UC8["SSE 流式 DM 叙述"]
        UC9["结构化数值检定"]
        UC10["场景推进"]
        UC11["剧情分支树可视化"]
        UC12["生图场景卡/NPC画像"]
        UC13["会话持久化/恢复"]
    end

    Player["玩家 (Actor)"]
    Player --> UC1
    Player --> UC2
    Player --> UC3
    Player --> UC4
    Player --> UC5
    Player --> UC6
    Player --> UC7
    UC2 .-> UC8 : <<include>>
    UC4 .-> UC9 : <<include>>
    UC9 .-> UC10 : <<extend>>
    UC2 .-> UC10 : <<extend>>
    UC8 .-> UC11 : <<include>>
    UC8 .-> UC12 : <<include>>
    UC1 .-> UC13 : <<include>>

    LLMAPI["外部 LLM API (DeepSeek/硅基流动)"]
    ImgAPI["外部生图 API (Kolors/FLUX)"]
    Timer["定时触发器 (预先生图预热)"]
    UC8 ---> LLMAPI
    UC12 --> ImgAPI
    Timer --> UC12 : 后台预热
```

### 1.2 系统数据流图 (DFD)

```mermaid
flowchart TD
    P["玩家输入(文本/指令)"]
    V["输入校验 + 提示词防护 (safety.py)"]
    CMD{"斜杠指令?"}
    G["玩法引擎 gameplay.py"]
    LLM["LLM Provider (mock/deepseek)"]
    PLAN["Pydantic 结构化 DMPlan"]
    CHECK["数值检定 Dice/Check (gameplay.py)"]
    ADV{"检定成功?"}
    SC["场景推进 scenario.py"]
    MEM["上下文记忆 memory.py"]
    SESS["会话 JSON 持久化 (persistence.py)"]
    TELE["SQLite 遥测 (check_log/session_metrics)"]
    SSE["SSE 流式输出 (main.py)"]
    IMG["生图 Provider (mock/remote)"]
    FRONT["前端 SPA (static/)"]
    BR["剧情分支树 /api/scenario/branches"]

    P --> V --> CMD
    CMD -- 是 --> G
    G --> SSE
    CMD -- 否 --> MEM --> LLM --> PLAN -->|建议检定| CHECK
    CHECK --> ADV
    ADV -- 是 --> SC
    CHECK --> TELE
    SC --> SESS
    SSE --> FRONT
    IMG --> FRONT
    BR --> FRONT
    SESS --> G
    SESS --> SSE
```

---

## 二、数据模型 (Data Model)

### 2.3 系统领域类图 (Domain Class Diagram)

```mermaid
classDiagram
    class GameSession {
        +str id
        +str title
        +float created_at/updated_at
        +SessionState state
        +list[Message] messages
        +dict stats
        +model_dump_json()
    }
    class SessionState {
        +str scene_id
        +int turn
        +PlayerState player
        +dict npcs
        +dict flags
        +list discovered
        +list skill_list
        +list events
    }
    class PlayerState {
        +str name
        +int hp
        +int max_hp
    }
    class Message {
        +str id
        +str kind
        +str role
        +str content
        +str meta
    }
    class DiceRoll {
        +str expression
        +int count/sides/modifier
        +list rolls
        +int total
    }
    class CheckResult {
        +str skill
        +int dc
        +DiceRoll roll
        +bool success
        +int margin
        +str degree
        +str narrative
    }
    class DMPlan {
        +str narrative
        +SkillProposal check
        +str advance_scene
        +list triggers
    }
    class SkillProposal {
        +str skill
        +str reason
        +int dc
    }
    class LLMProvider <<interface>> {
        +plan(session,text) DMPlan
        +stream_text(text) ~tokens
    }
    class MockLLMProvider
    class DeepSeekLLMProvider
    class ImageProvider <<interface>> {
        +scene_card(id) str
        +npc_portrait(id) str
    }
    class MockImageProvider
    class RemoteImageProvider
    class TelemetryStore {
        +log_check(...)
        +upsert_metrics(...)
        +query_checks(...)
    }
    class PersistenceService {
        +save_session(sess)
        +load_session(id) GameSession
    }

    GameSession "1" *-- "1" SessionState
    SessionState *-- PlayerState
    GameSession "1" o-- "many" Message
    CheckResult o-- DiceRoll
    DMPlan o-- SkillProposal
    DeepSeekLLMProvider ..|> LLMProvider
    MockLLMProvider ..|> LLMProvider
    RemoteImageProvider ..|> ImageProvider
    MockImageProvider ..|> ImageProvider
    TelemetryStore o-- GameSession
    PersistenceService o-- GameSession
```

### 2.4 数据库实体关系图 (ER Diagram / Schema)

```mermaid
erDiagram
    SESSIONS_JSON ||--o{ MESSAGES : contains
    SESSIONS_JSON ||--o{ SESSION_STATE : owns
    SESSION_STATE ||--o{ NPC_STATE : has

    SESSIONS_JSON {
        string id PK
        string title
        float created_at
        float updated_at
        string stats_json
    }
    MESSAGES {
        string id PK
        string session_id FK
        string kind
        string role
        string content
        string meta
    }
    SESSION_STATE {
        string session_id PK,FK
        string scene_id
        int turn
        int hp
        int max_hp
        string player
        string skills_json
    }

    CHECK_LOG {
        int id PK
        string session_id FK
        int turn
        string scene_id
        string skill
        int dc
        int total
        int success
        string degree
        string expression
        float ts
    }
    SESSION_METRICS {
        string session_id PK
        string player
        string scene_id
        int rolls
        int checks
        int passed
        int failed
        int big_success
        int big_failure
        int turns
        float updated_at
    }
    SESSIONS_JSON ||--o{ CHECK_LOG : "审计"
    SESSIONS_JSON ||--o| SESSION_METRICS : "汇总"
```

> 说明:会话正文为 JSON 文档(SESSIONS_JSON 逻辑实体,按 `data/sessions/{id}.json` 存储);
> `CHECK_LOG` / `SESSION_METRICS` 为 SQLite 物理表(`data/telemetry.db`),由 `storage.TelemetryStore` 维护;
> Pydantic 模型即上述实体的数据契约(`models.py`)。

---

## 三、动态/行为模型 (Dynamic Model)

### 3.5 端到端核心时序图 (System Sequence Diagram)

```mermaid
sequenceDiagram
    participant F as 前端 SPA
    participant S as FastAPI 服务
    participant L as LLM Provider
    participant C as 玩法引擎/数值检定
    participant I as 生图 Provider
    participant D as 会话持久化
    participant T as SQLite 遥测

    F->>S: POST /api/sessions {player_name}
    S->>D: 生成 GameSession + 开场消息
    S-->>F: 会话快照(场景卡 dataURL)
    loop 每个回合
        F->>S: POST /chat {text} (SSE)
        S->>S: 输入校验/守卫扫描
        alt 斜杠指令
            F->>S: POST /command {/roll,/check,/scene,...}
            S->>C: apply_command()
            S->>D: save_session()
            S-->>F: new_messages
        else 自由行动
            S->>L: plan(session, text) [异步]
            L-->>S: DMPlan(结构化)
            alt 建议检定
                S->>C: run_check(skill, dc)
                C-->>S: CheckResult(数值裁决)
                S->>T: log_check(...)
            end
            S->>C: 场景推进判定
            S->>D: save_session()
            S->>T: upsert_metrics(...)
            S-->>F: SSE token...token...done(会话+消息)
        end
    end
    F->>S: GET /api/scenario/branches
    S-->>F: 剧情分支树(节点+边)
    F->>S: GET /api/images/{name}
    S-->>F: 生图缓存 PNG (I 异步预生成)
```

### 3.6 系统生命周期状态机图 (State Diagram)

```mermaid
stateDiagram-v2
    [*] --> PENDING: POST /api/sessions
    PENDING --> READY: 开场剧情写入持久化
    READY --> RUNNING: 玩家提交自由行动
    RUNNING --> VALIDATING: 建议技能检定
    VALIDATING --> SUCCESS: 检定通过
    VALIDATING --> FAILURE: 检定失败
    SUCCESS --> ADVANCING: 满足推进条件
    FAILURE --> READY: 剧情继续
    ADVANCING --> READY: 场景推进并写入事件
    READY --> TERMINAL: 到达 end 场景
    TERMINAL --> [*]: /restart 重置会话
    RUNNING --> [*]: 服务异常/会话删除

    note right of PENDING
      会话状态机:会话级生命周期
      (START → PLAYING → END)
    end note
```

```mermaid
stateDiagram-v2
    [*] --> IDLE: 新建会话
    IDLE --> STREAMING: SSE 响应开启
    STREAMING --> IDLE: done 事件结束
    IDLE --> IDLE: /roll /check /scene
    STREAMING --> IDLE: 连接中断(客户端关闭)
```

---

## 4. 模块清单与目录映射

| 层 | 模块 | 职责 |
|---|---|---|
| presentation | `app/main.py`、`static/` | REST + SSE 路由、前端 SPA、分支树可视化 |
| application | `app/gameplay.py`、`app/providers.py` | 玩法裁决、LLM/生图 Provider、剧情推进 |
| domain | `app/models.py`、`app/scenario.py` | Pydantic 契约、剧本《雾中孤儿院》 |
| infrastructure | `app/persistence.py`、`app/storage.py`、`app/config.py` | JSON 持久化、SQLite 遥测、配置 |
| cross-cutting | `app/safety.py`、`app/rate_limit.py`、`app/memory.py` | 输入校验/守卫、频控、记忆窗口 |
| 质量 | `tests/`、`eval/`、`.github/` | Pytest/Behave、轨迹评测、CI |

## 5. 防御性编程与可靠性设计要点

- LLM 调用失败 → `DeepSeekLLMProvider.plan` 捕获异常并回退 `MockLLMProvider`。
- 生图失败 → `RemoteImageProvider.generate` 返回 False,路由层回退 mock SVG。
- 输入超长/控制字符 → `safety.sanitize_input` 抛 `InputValidationError`,由全局异常处理器转 422。
- 越狱/提示词注入 → `safety.scan_guardrails` 命中后角色内化解,不触发 LLM。
- 频控 → `SlidingWindowRateLimiter` 中间件返回 429。
- 遥测失败(如磁盘只读)→ `except` 吞掉并 warn,不影响主流程。
- 日志脱敏 → `safety.guard_log` 对疑似敏感内容打 `*masked*`。