"""IP-based rate limiter for public upload endpoints."""

import time
from collections import defaultdict

_requests: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(ip: str, max_per_hour: int = 20) -> bool:
    """Return True if request is allowed, False if rate limited."""
    now = time.time()
    # Prune old entries
    _requests[ip] = [t for t in _requests[ip] if now - t < 3600]
    if len(_requests[ip]) >= max_per_hour:
        return False
    _requests[ip].append(now)
    return True


def reset_rate_limits():
    """Reset all rate limits (for testing)."""
    _requests.clear()
