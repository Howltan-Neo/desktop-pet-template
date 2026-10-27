"""Small, testable timing rules for gaze and occasional autonomous actions."""
from __future__ import annotations

import math


QUIET_SECONDS = 600.0
AMBIENT_ACTIONS = ("fitness", "waiting", "sleep", "yawn", "stretch", "nuzzle")


def direction_index(dx: float, dy: float) -> int:
    """Zero points up, then sixteen directions clockwise like Xiaoan."""
    return int((math.degrees(math.atan2(dx, -dy)) % 360 + 11.25) // 22.5) % 16


def ambient_due(now: float, last_touch: float, last_ambient: float,
                *, enabled: bool, idle: bool, visible: bool) -> bool:
    return (enabled and idle and visible and
            now - max(last_touch, last_ambient) >= QUIET_SECONDS)
