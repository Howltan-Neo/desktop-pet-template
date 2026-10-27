"""Anonymous keyboard cadence detection, matching Xiaoan's thresholds."""
from __future__ import annotations

import ctypes
from collections import deque
from typing import Callable


# Only key-down counts are retained. Key identities and typed text are discarded.
TYPING_VKEYS = tuple(range(0x30, 0x3A)) + tuple(range(0x41, 0x5B)) + (
    0x08, 0x09, 0x0D, 0x20,
) + tuple(range(0xBA, 0xC1)) + tuple(range(0xDB, 0xE0))


class KeyboardActivity:
    def __init__(self, key_state: Callable[[int], int] | None = None,
                 threshold: int = 3, window: float = 3.5,
                 active_seconds: float = 2.5) -> None:
        self.key_state = key_state or ctypes.windll.user32.GetAsyncKeyState
        self.threshold = threshold
        self.window = window
        self.active_seconds = active_seconds
        self.previous: set[int] | None = None
        self.downs: deque[float] = deque()
        self.active_until = 0.0

    def poll(self, now: float) -> bool:
        pressed: set[int] = set()
        recent: set[int] = set()
        for key in TYPING_VKEYS:
            value = self.key_state(key)
            if value & 0x8000:
                pressed.add(key)
            if value & 0x0001:
                recent.add(key)
        if self.previous is None:
            self.previous = pressed
            return False
        new_downs = (pressed - self.previous) | (recent - self.previous)
        self.previous = pressed
        self.downs.extend([now] * len(new_downs))
        while self.downs and now - self.downs[0] > self.window:
            self.downs.popleft()
        if len(self.downs) >= self.threshold and new_downs:
            self.active_until = now + self.active_seconds
        return now < self.active_until
