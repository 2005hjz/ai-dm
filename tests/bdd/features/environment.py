"""BDD 环境:每个场景前启动 TestClient,放行限流,避免触发 429。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import app.main as main_mod  # noqa: E402


def before_all(context):
    # 放行限流:BDD 验收场景不触发 429
    main_mod._limiter = main_mod.SlidingWindowRateLimiter(limit=10**6)


def before_scenario(context, scenario):
    context.client = TestClient(main_mod.app)


def after_scenario(context, scenario):
    context.client.close()
    context.client = None
