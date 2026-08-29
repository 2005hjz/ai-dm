# US01 — 创建会话与开场剧情引导

> Sprint: 1   ·   Story Points: 2(M)   ·   Owner: @ai-dm-core   ·   Status: Done(CI 验证)

## INVEST 原则核对
- **I**ndependent:不依赖其他故事,可独立验收
- **N**egotiable:开场文案、默认玩家名可调整
- **V**aluable:玩家获得可恢复的跑团现场,是所有游戏行为的前提
- **E**stimable:工作量 ≤ 2SP,边界清晰
- **S**mall:仅覆盖「会话生命周期 + 开场引导」
- **T**estable:Gherkin 场景可自动执行

## 3C — Card / Conversation / Confirmation
- **Card**:作为玩家,我想要创建一个新跑团会话并获得开场剧情与操作引导,以便随时开始一局《雾中孤儿院》。
- **Conversation**:前端点击「开始新冒险」→ `POST /api/sessions`;服务端生成 `GameSession`,注入 `scene_id=prologue` 与开场消息和 `/roll`、`/check`、`/scene`、`/hp`、`/help`、`/restart` 指令说明;会话以 JSON 落盘,重启服务可恢复。
- **Confirmation**(验收标准):
  1. 返回会话快照含 `id / title / state(player, scene_id=prologue)`。
  2. 消息列表中至少包含一条开场叙述(含「铁门」「雾」)。
  3. 消息列表中至少包含一条 `system` 指令引导消息。
  4. 持久化目录生成 `data/sessions/{id}.json`,重启后可恢复。
  5. 空/超长玩家名被安全层 422 拦截。

## Gherkin (BDD)
```gherkin
# language: zh-CN
功能: 会话创建
  场景: 玩家创建会话并开始冒险
    当 我发起新会话 且玩家名为「阿梅」
    那么 会话应该以场景 "prologue" 开始
    并且 返回的问候中包含铁门与雾的叙事
    并且 会话中有一条系统指令消息
```

---

## 六图精细化建模

### 1) 故事级用例/边界图 (Story Context & Scope)
```mermaid
sequenceDiagram
    autonumber
    participant F as 前端 SPA
    participant S as FastAPI `/api/sessions`
    participant P as persistence.py
    participant G as gameplay.start_session()
    participant T as telemetry (session_metrics)

    F->>S: POST /api/sessions {player_name}
    S->>S: safety.sanitize_input(player_name)
    alt 名称非法(空/超长/控制字符)
        S-->>F: 422 InputValidationError
    else 合法
        S->>G: start_session(new_id, name)
        G->>G: 初始化 SessionState(prologue/npcs/skills)
        G->>G: 写入开场叙述 + system 引导
        S->>P: save_session(sess)
        S->>T: upsert_metrics(...)
        S-->>F: 200 {id, title, state, scene, messages[]}
    end
```

### 2) 故事级组件/数据流图 (Story Component / Data Flow Diagram)
```mermaid
flowchart TD
    UI["新冒险按钮 + 玩家名输入"] -->|player_name| RT["POST /api/sessions"]
    RT --> VAL["safety.sanitize_input(校验:空/长/控制字符)"]
    VAL -- 非法 --> ERR["422 JSON 错误"]
    VAL -- 合法 --> START["gameplay.start_session()"]
    START --> SC["SCENARIO['prologue'] 开场文案"]
    START --> SYS["system 指令引导消息"]
    START --> STATE["SessionState(scene_id, npcs, skills)"]
    STATE --> JS["data/sessions/{id}.json"]
    STATE --> TELE["session_metrics 表"]
    JS --> RES["会话快照 + messages 响应"]
    ERR --> UI
    RES --> UI
```

### 3) 故事级领域类与 Pydantic 数据契约图
```mermaid
classDiagram
    class GameSession {
        +str id
        +str title
        +datetime created_at
        +SessionState state
        +list[Message] messages
        +dict stats
    }
    class SessionState {
        +str scene_id = "prologue"
        +int turn = 0
        +PlayerState player
        +dict npcs
        +list[str] skill_list
    }
    class PlayerState {
        +str name
        +int hp = 5
        +int max_hp = 5
    }
    class Message {
        +str id
        +str kind  "story|player|system|roll|check|card"
        +str role
        +str content
    }
    GameSession "1" *-- "1" SessionState
    GameSession "1" *-- "many" Message
    SessionState "1" *-- "1" PlayerState
```

### 4) 故事级数据实体/持久化模型
```mermaid
erDiagram
    SESSIONS_JSON ||--o{ MESSAGES : "会话1..N消息"
    SESSIONS_JSON ||--|| SESSION_STATE : "1:1 状态"
    SESSION_STATE {
        string scene_id "prologue"
        int turn
        string player_name
        int hp
    }
    SESSION_METRICS {
        string session_id PK
        string player
        string scene_id
        int turns
    }
    SESSIONS_JSON {
        string id PK
        string title
        string stats_json
    }
```

### 5) 故事级端到端时序交互图
(同 1 图完整时序,见上 `sequenceDiagram`——本故事只与持久化/遥测交互,不触发 LLM 与外部 API,故无第三方请求。)

### 6) 故事级状态机与活动流程图
```mermaid
stateDiagram-v2
    [*] --> INVALID: 名称非法
    INVALID --> [*]: 422 拒绝
    [*] --> DRAFTING: 合法名称
    DRAFTING --> PERSISTED: 写入 JSON + 遥测
    PERSISTED --> READY: 返回会话快照
    READY --> [*]: 等待玩家自由行动(交棒 US02/US03)

    note right of DRAFTING
      活动:初始化 State → 写入开场消息 → 解析指令消息
    end note
```

## 交付物与测试链接
- 实现:`app/gameplay.py:start_session`、`app/main.py:POST /api/sessions`、`app/persistence.py`
- 单元测试:`tests/unit/test_gameplay.py::test_start_session_seed_state`、`tests/unit/test_api.py::test_create_and_get_session`
- BDD 验收:`tests/bdd/features/core_rpg.feature`「玩家创建会话并开始冒险」
- 评测轨迹:`eval/evalset.json` tr-01