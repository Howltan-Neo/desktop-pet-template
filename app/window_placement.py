"""Position floating pet windows across the entire Windows virtual desktop."""
from __future__ import annotations

import ctypes
import ctypes.wintypes


def virtual_screen_bounds() -> tuple[int, int, int, int]:
    user32 = ctypes.windll.user32
    left = user32.GetSystemMetrics(76)
    top = user32.GetSystemMetrics(77)
    width = user32.GetSystemMetrics(78)
    height = user32.GetSystemMetrics(79)
    if width <= 0 or height <= 0:
        return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    return left, top, left + width, top + height


def clamp_pet_position(x: int, y: int, size: tuple[int, int],
                       bounds: tuple[int, int, int, int], visible: int = 60) -> tuple[int, int]:
    left, top, right, bottom = bounds
    width, _ = size
    return (max(left - width + visible, min(right - visible, x)),
            max(top, min(bottom - visible, y)))


def monitor_areas(hwnd: int) -> tuple[tuple[int, int, int, int],
                                     tuple[int, int, int, int]]:
    class MonitorInfo(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.wintypes.DWORD),
                    ("rcMonitor", ctypes.wintypes.RECT),
                    ("rcWork", ctypes.wintypes.RECT),
                    ("dwFlags", ctypes.wintypes.DWORD)]
    try:
        user32 = ctypes.windll.user32
        user32.MonitorFromWindow.argtypes = [ctypes.c_void_p, ctypes.wintypes.DWORD]
        user32.MonitorFromWindow.restype = ctypes.c_void_p
        user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MonitorInfo)]
        user32.GetMonitorInfoW.restype = ctypes.wintypes.BOOL
        monitor = user32.MonitorFromWindow(ctypes.c_void_p(hwnd), 2)
        info = MonitorInfo()
        info.cbSize = ctypes.sizeof(MonitorInfo)
        if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            screen, work = info.rcMonitor, info.rcWork
            return ((screen.left, screen.top, screen.right, screen.bottom),
                    (work.left, work.top, work.right, work.bottom))
    except (AttributeError, OSError):
        pass
    bounds = virtual_screen_bounds()
    return bounds, bounds


def monitor_work_area(hwnd: int) -> tuple[int, int, int, int]:
    return monitor_areas(hwnd)[1]


def dock_position(monitor: tuple[int, int, int, int],
                  work: tuple[int, int, int, int], size: int,
                  margin: int = 12, taskbar_reserve: int = 48) -> tuple[int, int]:
    """Leave room for a visible or auto-hidden bottom taskbar."""
    left, top, right, bottom = work
    bottom = min(bottom, monitor[3] - bottom_taskbar_height(monitor, taskbar_reserve))
    return (max(left + margin, right - size - margin),
            max(top + margin, bottom - size - margin))


def bottom_taskbar_height(monitor, fallback=48):
    """Inspect each monitor's shell taskbar, including auto-hidden taskbars."""
    try:
        user32 = ctypes.windll.user32
        heights = []
        callback_type = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        def visit(hwnd, _):
            name = ctypes.create_unicode_buffer(128)
            user32.GetClassNameW(hwnd, name, len(name))
            if name.value in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
                rect = ctypes.wintypes.RECT()
                if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    overlap = min(rect.right, monitor[2]) - max(rect.left, monitor[0])
                    height = rect.bottom - rect.top
                    if overlap > (monitor[2]-monitor[0]) / 2 and rect.top >= monitor[1] + (monitor[3]-monitor[1])/2 and 0 < height < 240:
                        heights.append(height)
            return True
        user32.EnumWindows(callback_type(visit), 0)
        return max(heights, default=fallback)
    except (AttributeError, OSError):
        return fallback


def card_position(pet: tuple[int, int, int, int], card: tuple[int, int],
                  work: tuple[int, int, int, int]) -> tuple[int, int]:
    px1, py1, px2, py2 = pet
    cw, ch = card
    left, top, right, bottom = work
    edge, gap = 8, 14
    clamp_x = lambda x: max(left + edge, min(right - cw - edge, x))
    clamp_y = lambda y: max(top + edge, min(bottom - ch - edge, y))
    sides = [(px1 - gap - cw, clamp_y((py1 + py2 - ch) // 2)),
             (px2 + gap, clamp_y((py1 + py2 - ch) // 2))]
    if (px1 + px2) / 2 < (left + right) / 2:
        sides.reverse()
    for x, y in sides:
        if left + edge <= x and x + cw <= right - edge:
            return x, y
    vertical = [(clamp_x((px1 + px2 - cw) // 2), py1 - gap - ch),
                (clamp_x((px1 + px2 - cw) // 2), py2 + gap)]
    for x, y in vertical:
        if top + edge <= y and y + ch <= bottom - edge:
            return x, y
    return clamp_x(px1 - gap - cw), clamp_y(py1)
