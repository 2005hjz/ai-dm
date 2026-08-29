"""全局配置:基于环境变量 + .env 文件,切换 LLM/生图提供方。

设计要点:
- 未配置任何 API Key → 自动回退 mock 模式,离线也可完整跑通全流程(CI/冒烟/答辩演示)。# noqa: E501
- 配置真实 Key(DeepSeek / 硅基流动均走 OpenAI 兼容接口)→ 走真实模型。
- 所有可调参数来自环境变量,便于 Docker / docker-compose 编排注入。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
_loaded = load_dotenv(BASE_DIR / ".env", override=False)

DATA_DIR = BASE_DIR / "data"
SESSION_DIR = DATA_DIR / "sessions"
IMAGE_CACHE_DIR = DATA_DIR / "images"
DATA_DIR.mkdir(exist_ok=True)
SESSION_DIR.mkdir(exist_ok=True)
IMAGE_CACHE_DIR.mkdir(exist_ok=True)

# ---- LLM 提供方 ----
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock").strip().lower()  # mock | deepseek
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip().rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.8"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "600"))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))

# ---- 图片生成提供方 ----
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "mock").strip().lower()  # mock | remote
IMAGE_API_KEY = os.getenv("IMAGE_API_KEY", "").strip()
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL", "https://api.siliconflow.cn/v1").strip().rstrip("/")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "Kwai-Kolors/Kolors").strip()
IMAGE_SIZE = os.getenv("IMAGE_SIZE", "768x512").strip()

# ---- 服务 ----
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# ---- 上下文记忆管理 ----
MAX_MESSAGES_IN_CONTEXT = int(os.getenv("MAX_MESSAGES_IN_CONTEXT", "30"))
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "4000"))
SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", str(24 * 60)))

# ---- 防御性编程 ----
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
MAX_INPUT_LENGTH = int(os.getenv("MAX_INPUT_LENGTH", "500"))
TELEMETRY_ENABLED = os.getenv("TELEMETRY_ENABLED", "true").strip().lower() in ("1", "true", "yes")


# ---- 派生:deepseek 接口归一(DeepSeek 官方与硅基流动端点兼容 /v1/chat/completions) ----
def chat_url(base: str) -> str:
    """归一化 OpenAI 兼容聊天补全端点地址。"""
    b = base.rstrip("/")
    if b.endswith("/chat/completions"):
        return b
    if b.endswith("/v1"):
        return f"{b}/chat/completions"
    return f"{b}/v1/chat/completions"


DEEPSEEK_CHAT_URL = chat_url(DEEPSEEK_BASE_URL)

# ---- 派生:图片生成接口 ----
IMAGE_GEN_URL = IMAGE_BASE_URL + "/images/generations"


def active_provider() -> str:
    """当前生效的模型提供方名称(mock 或 deepseek)。"""
    return LLM_PROVIDER if (LLM_PROVIDER == "remote" or (LLM_PROVIDER == "deepseek" and DEEPSEEK_API_KEY)) else "mock"


def active_image_provider() -> str:
    return IMAGE_PROVIDER if (IMAGE_PROVIDER == "remote" and IMAGE_API_KEY) else "mock"
