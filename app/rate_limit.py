"""API 频控(滑动窗口限流),防御性编程的一部分。

按客户端 IP 做分钟级滑动窗口,超限返回 429。纯内存实现,重启即清零,
适合单机/容器场景;生产可替换为 Redis 等分布式实现。
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from . import config


class SlidingWindowRateLimiter:
    def __init__(self, limit: int | None = None):
        self.limit = limit if limit is not None else config.RATE_LIMIT_PER_MINUTE
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> tuple[bool, int]:
        """返回 (是否放行, 当前窗口内剩余可调用次数)。"""
        if self.limit <= 0:
            return True, -1
        now = time.monotonic()
        dq = self._hits[key]
        while dq and now - dq[0] > 60:
            dq.popleft()
        if len(dq) >= self.limit:
            return False, 0
        dq.append(now)
        return True, self.limit - len(dq)

    def reset(self) -> None:
        self._hits.clear()
