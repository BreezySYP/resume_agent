"""shared/safety/rate_limiter.py"""
from collections import defaultdict
import time


class RateLimiter:
    def __init__(self, requests_per_minute: int = 40):
        self.limit    = requests_per_minute
        self.requests = defaultdict(list)

    def check(self, user_id: str = "default") -> bool:
        now = time.time()
        self.requests[user_id] = [t for t in self.requests[user_id] if now - t < 60]
        if len(self.requests[user_id]) >= self.limit:
            return False
        self.requests[user_id].append(now)
        return True


rate_limiter = RateLimiter()
