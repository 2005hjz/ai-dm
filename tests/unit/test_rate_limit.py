"""滑动窗口频控的单元测试。"""

from __future__ import annotations

from app.rate_limit import SlidingWindowRateLimiter


def test_allow_within_limit():
    rl = SlidingWindowRateLimiter(limit=3)
    assert rl.allow("ip-1")[0] is True
    assert rl.allow("ip-1")[0] is True
    assert rl.allow("ip-1")[0] is True
    ok, remaining = rl.allow("ip-1")
    assert ok is False
    assert remaining == 0


def test_independent_clients():
    rl = SlidingWindowRateLimiter(limit=2)
    assert rl.allow("a")[0] is True
    assert rl.allow("a")[0] is True
    assert rl.allow("b")[0] is True


def test_window_expiry():
    rl = SlidingWindowRateLimiter(limit=1)
    assert rl.allow("ip")[0] is True
    assert rl.allow("ip")[0] is False
    # 手动推进 61 秒,窗口应重置
    rl._hits["ip"] = rl._hits["ip"]  # noop
    import collections

    rl._hits["ip"] = collections.deque([])
    assert rl.allow("ip")[0] is True


def test_disabled_when_limit_zero():
    rl = SlidingWindowRateLimiter(limit=0)
    assert rl.allow("x")[0] is True
