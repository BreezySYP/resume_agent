"""shared.safety.rate_limiter 测试。"""
import time

from shared.safety.rate_limiter import RateLimiter


def test_allows_until_limit(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(time, "time", lambda: now[0])

    limiter = RateLimiter(requests_per_minute=2)
    assert limiter.check("u1") is True
    assert limiter.check("u1") is True
    assert limiter.check("u1") is False


def test_window_slides_after_60s(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(time, "time", lambda: now[0])

    limiter = RateLimiter(requests_per_minute=1)
    assert limiter.check("u1") is True
    assert limiter.check("u1") is False

    now[0] += 61
    assert limiter.check("u1") is True


def test_users_isolated(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(time, "time", lambda: now[0])

    limiter = RateLimiter(requests_per_minute=1)
    assert limiter.check("u1") is True
    assert limiter.check("u2") is True
    assert limiter.check("u1") is False
