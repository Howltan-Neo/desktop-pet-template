"""Character-independent Windows desktop companion using shared glass panels."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import math
import os
import queue
import random
import shutil
import sys
import time
import tkinter as tk
import traceback
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageTk

from activity_logic import AMBIENT_ACTIONS, ambient_due, direction_index
from glass_popup import GlassPopup
from keyboard_activity import KeyboardActivity
from speech_card import SpeechCard
from window_placement import (card_position, clamp_pet_position, dock_position,
                              monitor_areas, monitor_work_area, virtual_screen_bounds)

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError, OSError):
    pass

try:
    import pystray
    from pystray._win32 import Icon as Win32TrayIcon
    from pystray._util import win32 as tray_win32
except ImportError:
    pystray = None


if pystray is not None:
    class TemplateTrayIcon(Win32TrayIcon):
        def __init__(self, *args, on_left=None, on_right=None, **kwargs):
            self.on_left, self.on_right = on_left, on_right
            super().__init__(*args, **kwargs)

        def _on_notify(self, wparam, lparam):
            if lparam == tray_win32.WM_RBUTTONUP and self.on_right:
                self.on_right()
            elif lparam == tray_win32.WM_LBUTTONUP and self.on_left:
                self.on_left()


from character_pack import selected_pack
PACK = selected_pack()
APP_NAME = PACK.name
BASE_SIZE = 265
MIN_SIZE, MAX_SIZE = round(BASE_SIZE * .65), round(BASE_SIZE * 1.65)
KEY = "#010203"
CONFIG = PACK.settings_path
NORMAL = [(key, value.get("label", key), next(iter(value.get("dialogue", [])), ""))
          for key, value in PACK.actions.items() if key != "look_direction"]
DOG = NORMAL
def frame_count(key):
    return len(PACK.action(key)["frames"])

def settings_load() -> dict:
    defaults = {"dog": False, "topmost": True, "active": True, "size": BASE_SIZE,
                "size_schema": 1, "x": None, "y": None}
    found = {}
    try:
        found = json.loads(CONFIG.read_text(encoding="utf-8"))
        if isinstance(found, dict):
            defaults.update({key: found[key] for key in defaults.keys() & found.keys()})
    except (OSError, ValueError, TypeError):
        pass
    # Migrate the former 71% minimum and 280px default only once.
    if not isinstance(found, dict) or found.get("size_schema") != 1:
        if defaults["size"] in (350, 280):
            defaults["size"] = BASE_SIZE
        elif defaults["size"] == 200:
            defaults["size"] = MIN_SIZE
    try:
        requested_size = int(defaults["size"])
    except (TypeError, ValueError):
        requested_size = BASE_SIZE
    defaults["size"] = max(MIN_SIZE, min(MAX_SIZE, requested_size))
    return defaults


def settings_save(values: dict) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    temp = CONFIG.with_suffix(".tmp")
    temp.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(CONFIG)


def prepare_cursor_specs():
    shared = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "assets"
    folder = CONFIG.parent / "cursors"
    folder.mkdir(parents=True, exist_ok=True)
    result = {}
    for kind in ("head", "head_pressed", "body"):
        configured = PACK.data.get("cursors", {}).get(kind)
        source = PACK.path(configured) if configured else shared / (kind + ".cur")
        if source.is_file():
            target = folder / (kind + ".cur")
            shutil.copyfile(source, target)
            result[kind] = "@" + target.as_posix()
        else:
            result[kind] = "hand2"
    return result

def acquire_instance():
    if os.name != "nt":
        return None
    kernel = ctypes.windll.kernel32
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.wintypes.BOOL, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel.CreateMutexW(None, True, "Local\\DesktopPetTemplate_" + PACK.id)
    return None if kernel.GetLastError() == 183 else handle

def validate_resources():
    from pack_validation import validate
    return validate(PACK.root)


class DesktopPet:
    def __init__(self):
        self.settings = settings_load()
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.overrideredirect(True)
        self.root.configure(bg=KEY)
        self.root.wm_attributes("-transparentcolor", KEY)
        self.dog = False
        self.topmost = bool(self.settings["topmost"])
        self.active = bool(self.settings["active"])
        self.size = self.settings["size"]
        self.root.attributes("-topmost", self.topmost)
        bounds = virtual_screen_bounds()
        default_x = bounds[2] - self.size - 75
        default_y = bounds[3] - self.size - 85
        x = self.settings["x"] if isinstance(self.settings["x"], int) else default_x
        y = self.settings["y"] if isinstance(self.settings["y"], int) else default_y
        x, y = clamp_pet_position(x, y, (self.size, self.size), bounds)
        self.root.geometry(f"{self.size}x{self.size}+{x}+{y}")
        self.canvas = tk.Canvas(self.root, width=self.size, height=self.size, bg=KEY,
                                highlightthickness=0, bd=0, cursor="arrow")
        self.canvas.pack()
        self.image_id = self.canvas.create_image(self.size // 2, self.size // 2)
        self.cache = {}
        self.photo = None
        self.display_key = None
        self.pose = "idle"
        self.pose_until = 0.0
        self.frame = 0
        self.frame_last = 0.0
        self.ear_sequence = None
        self.ear_after = None
        self.run_frame = 1
        self.run_last = 0.0
        self.press = None
        self.dragged = False
        self.hover_zone = ""
        self.hover_after = None
        self.hold_after = None
        self.hold_triggered = False
        self.click_after = None
        self.last_touch = time.monotonic()
        self.last_ambient = self.last_touch
        self.keyboard_activity = KeyboardActivity()
        self.keyboard_active = False
        self.next_keyboard_sample = self.last_touch
        self.work_source = None
        self.look_index = 0
        self.look_until = 0.0
        self.last_left_down = False
        self.external_drag_origin = None
        self.press_started = 0.0
        self.hit_masks = {}
        self.hit_mask = None
        self.pressed_cursor_after = None
        self.glass_menu = None
        self.glass_actions = None
        self.glass_tray = None
        self.action_page = 0
        self.dialogue = PACK.dialogue
        self.bubble_card = SpeechCard(self.root)
        self.bubble_after = None
        self.tray = None
        self.tray_queue = queue.Queue()
        self.cursor_specs = prepare_cursor_specs()
        for kind, spec in list(self.cursor_specs.items()):
            try:
                self.canvas.configure(cursor=spec)
            except tk.TclError:
                self.cursor_specs[kind] = "hand2"
        self.canvas.configure(cursor="arrow")
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Leave>", self.on_leave)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double)
        self.canvas.bind("<Button-3>", self.open_glass_menu)
        self.root.bind("<Escape>", lambda _e: self.close_panels())
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.show_pose("idle", seconds=0)
        self.start_tray()
        self.root.after(50, self.tick)
        self.root.after(150, self.poll_tray)

    def save(self):
        self.settings.update(dog=self.dog, topmost=self.topmost, active=self.active,
                             size=self.size, x=self.root.winfo_x(), y=self.root.winfo_y())
        settings_save(self.settings)

    def sprite(self, key, frame=None):
        path = PACK.frame_path(key, frame or 0)
        cache_key = (str(path), self.size)
        if cache_key not in self.cache:
            with Image.open(path) as source:
                art = source.convert("RGBA").resize((self.size, self.size), Image.Resampling.LANCZOS)
            art.putalpha(art.getchannel("A").point(lambda a: 255 if a >= 96 else 0))
            self.cache[cache_key] = ImageTk.PhotoImage(art, master=self.root)
        return self.cache[cache_key]


    def interaction_mask(self, key):
        if key not in self.hit_masks:
            mask = Image.new("L", (512, 512))
            for index in range(frame_count(key)):
                with Image.open(PACK.frame_path(key, index)) as source:
                    visible = source.getchannel("A").resize((512, 512)).point(lambda a: 255 if a >= 96 else 0)
                mask = ImageChops.lighter(mask, visible)
            self.hit_masks[key] = mask.filter(ImageFilter.MaxFilter(9))
        return self.hit_masks[key]


    def show_pose(self, key, seconds=None, words=None):
        key = PACK.resolve_action(key)
        if seconds is None:
            seconds = {"sleep": 8.0, "work": 7.0, "fitness": 5.2,
                       "waiting": 12.0, "sad": 8.0}.get(key, max(4.0, frame_count(key) * self.frame_interval(key) + .3))
        if self.ear_after is not None and not key.startswith("ear_"):
            self.root.after_cancel(self.ear_after)
            self.ear_after = None
            self.ear_sequence = None
        if key != self.pose:
            self.frame = 0
            self.frame_last = time.monotonic()
        self.pose = key
        self.hit_mask = self.interaction_mask("look_direction" if key == "look" else key)
        self.pose_until = time.monotonic() + seconds if seconds else float("inf")
        display = ("look_direction", self.look_index) if key == "look" else (key, self.frame)
        self.photo = self.sprite(*display)
        self.display_key = display
        self.canvas.itemconfigure(self.image_id, image=self.photo)
        if words is None:
            catalog = DOG if self.dog else NORMAL
            fallback = next((line for k, _name, line in catalog if k == key), "")
            words = self.dialogue.next("dog" if self.dog else "normal", key, fallback)
        if words:
            self.say(words)

    def zone(self, x, y):
        qx, qy = round(x * 512 / self.size), round(y * 512 / self.size)
        if not (0 <= qx < 512 and 0 <= qy < 512) or self.hit_mask is None or not self.hit_mask.getpixel((qx,qy)):
            return "outside"
        for region in PACK.hotzones:
            left, top, right, bottom = region["rect"]
            if left <= qx <= right and top <= qy <= bottom:
                return region["action"]
        return "body"


    def set_interaction_cursor(self, zone, pressed=False):
        if zone.startswith(("pet_", "ear_")):
            kind = "head_pressed" if pressed else "head"
        else:
            kind = "body" if zone != "outside" else "arrow"
        spec = self.cursor_specs.get(kind, "arrow")
        if str(self.canvas.cget("cursor")) != spec:
            self.canvas.configure(cursor=spec)

    def cancel_pressed_cursor(self):
        if self.pressed_cursor_after is not None:
            self.root.after_cancel(self.pressed_cursor_after)
            self.pressed_cursor_after = None

    def touch(self, zone):
        self.last_touch = self.last_ambient = time.monotonic()
        self.work_source = None
        if zone == "body":
            zone = PACK.interactions.get("click", "wave")
        if zone != "outside":
            self.show_pose(zone)


    def on_motion(self, event):
        if self.press is not None:
            return
        zone = self.zone(event.x, event.y)
        self.set_interaction_cursor(zone)
        if zone == self.hover_zone:
            return
        self.hover_zone = zone
        if self.hover_after is not None:
            self.root.after_cancel(self.hover_after)
            self.hover_after = None
        if zone.startswith("pet_"):
            self.hover_after = self.root.after(650, lambda z=zone: self.touch(z) if self.hover_zone == z and self.press is None else None)

    def on_leave(self, _event):
        self.hover_zone = ""
        if self.hover_after is not None:
            self.root.after_cancel(self.hover_after)
            self.hover_after = None
        self.set_interaction_cursor("outside")

    def on_press(self, event):
        self.cancel_pressed_cursor()
        if self.work_source == "keyboard":
            self.work_source = None
            self.show_pose("idle", seconds=0, words="")
        self.press = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y(), self.zone(event.x, event.y))
        self.press_started = time.monotonic()
        self.dragged = False
        self.hold_triggered = False
        self.work_source = None
        self.set_interaction_cursor(self.press[4], pressed=True)
        if self.press[4].startswith("pet_"):
            def rub():
                if self.press and not self.dragged:
                    self.hold_triggered = True
                    self.show_pose(PACK.interactions.get("hold", "pet_front"), seconds=2.0)
            self.hold_after = self.root.after(680, rub)

    def on_drag(self, event):
        if self.press is None:
            return
        px, py, wx, wy, _ = self.press
        dx, dy = event.x_root - px, event.y_root - py
        if abs(dx) + abs(dy) < 6:
            return
        self.dragged = True
        self.look_until = 0.0
        self.set_interaction_cursor("body")
        if self.hold_after is not None:
            self.root.after_cancel(self.hold_after)
            self.hold_after = None
        x, y = clamp_pet_position(wx + dx, wy + dy, (self.size, self.size), virtual_screen_bounds())
        self.root.geometry(f"+{x}+{y}")
        direction = "run_left" if dx < 0 else "run_right"
        if self.pose != direction:
            self.show_pose(direction, seconds=.6, words="")
        else:
            self.pose_until = time.monotonic() + .6
        self.bubble_card.hide()
        if self.bubble_after is not None:
            self.root.after_cancel(self.bubble_after)
            self.bubble_after = None

    def on_release(self, event):
        if self.press is None:
            return
        if self.hold_after is not None:
            self.root.after_cancel(self.hold_after)
            self.hold_after = None
        was_dragged = self.dragged
        was_held = self.hold_triggered
        press_zone = self.press[4]
        self.press = None
        self.last_touch = time.monotonic()
        release_zone = self.zone(event.x, event.y)
        if (not was_dragged and press_zone.startswith(("pet_", "ear_"))
                and release_zone == press_zone):
            self.set_interaction_cursor(release_zone, pressed=True)
            def restore_cursor():
                self.pressed_cursor_after = None
                if self.press is None and self.root.winfo_exists():
                    self.set_interaction_cursor(release_zone)
            self.pressed_cursor_after = self.root.after(180, restore_cursor)
        else:
            self.set_interaction_cursor(release_zone)
        if was_dragged:
            self.last_touch = time.monotonic()
            self.root.after(420, lambda: self.show_pose("idle", seconds=0, words="")
                            if self.press is None and self.pose.startswith("run_") else None)
            self.save()
            return
        if was_held:
            return
        if self.click_after is not None:
            self.root.after_cancel(self.click_after)
        self.click_after = self.root.after(210, lambda: self.touch(release_zone))

    def on_double(self, _event):
        if self.click_after is not None:
            self.root.after_cancel(self.click_after)
            self.click_after = None
        self.last_touch = time.monotonic()
        self.work_source = None
        self.show_pose(PACK.interactions.get("double_click", "wave"))

    def say(self, words):
        if self.bubble_after is not None:
            self.root.after_cancel(self.bubble_after)
        area = monitor_work_area(self.root.winfo_id())
        px, py = self.root.winfo_x(), self.root.winfo_y()
        self.bubble_card.show(words, (px, py, px + self.size, py + self.size),
                              area, self.size / BASE_SIZE, self.dog)
        self.bubble_after = self.root.after(3300, self.bubble_card.hide)

    # Shared glass popup layout and input model.
    def glass_state(self):
        return {"scale": self.size / BASE_SIZE, "proactive": self.active,
                "topmost": self.topmost, "dog": self.dog,
                "actions": [(key, label) for key, label, _ in (DOG if self.dog else NORMAL)],
                "page": self.action_page}

    def glass_avatar(self):
        with Image.open(PACK.frame_path("idle", 0)) as source:
            art = source.convert("RGBA")
        bounds = art.getchannel("A").getbbox()
        return art.crop(bounds) if bounds else art


    def open_glass_menu(self, _event=None):
        self.close_panels()
        size = (420, 670)
        area = monitor_work_area(self.root.winfo_id())
        pet = (self.root.winfo_x(), self.root.winfo_y(),
               self.root.winfo_x() + self.size, self.root.winfo_y() + self.size)
        pos = card_position(pet, size, area)
        self.glass_menu = GlassPopup(self.root, "menu", size, pos,
                                     self.glass_avatar(), self.glass_state,
                                     self.glass_menu_action, work_area=area)

    def open_glass_actions(self):
        self.close_panels()
        self.action_page = 0
        size = (420, 720)
        area = monitor_work_area(self.root.winfo_id())
        pet = (self.root.winfo_x(), self.root.winfo_y(),
               self.root.winfo_x() + self.size, self.root.winfo_y() + self.size)
        pos = card_position(pet, size, area)
        self.glass_actions = GlassPopup(self.root, "actions", size, pos,
                                        self.glass_avatar(), self.glass_state,
                                        self.glass_actions_action, work_area=area)

    def open_glass_tray(self):
        self.close_panels()
        size = (340, 480)
        area = virtual_screen_bounds()
        mx, my = self.root.winfo_pointerxy()
        x = max(area[0] + 5, min(area[2] - size[0] - 5, mx - size[0] + 18))
        y = max(area[1] + 5, min(area[3] - size[1] - 5, my - size[1] + 6))
        self.glass_tray = GlassPopup(self.root, "tray", size, (x, y),
                                     self.glass_avatar(), self.glass_state,
                                     self.glass_tray_action, work_area=area)

    def toggle_dog(self):
        from tkinter import filedialog, messagebox
        folder = filedialog.askdirectory(parent=self.root, title="选择含 character.json 的角色包")
        if not folder:
            return
        from pack_validation import validate
        report = validate(Path(folder))
        if not report["ok"]:
            messagebox.showerror("角色包检查失败", "\n".join(report["errors"][:8]), parent=self.root)
            return
        import subprocess
        self.save()
        command = [sys.executable]
        if not getattr(sys, "frozen", False):
            command.append(str(Path(__file__).resolve().parents[1] / "run.py"))
        command.extend(["--pack", folder])
        self.quit()
        subprocess.Popen(command)


    def dock(self):
        self.root.deiconify()
        self.root.update_idletasks()
        monitor, work = monitor_areas(self.root.winfo_id())
        x, y = dock_position(monitor, work, self.size)
        self.root.geometry(f"+{x}+{y}")
        self.root.update_idletasks()
        self.root.lift()
        self.last_touch = time.monotonic()
        self.save()
        self.close_panels()
        self.say(PACK.message("dock", "我在这里陪着你。"))

    def glass_common_action(self, name, value):
        self.last_touch = time.monotonic()
        if name == "close":
            self.close_panels()
        elif name == "chat":
            self.say(self.dialogue.next("dog" if self.dog else "normal", "idle"))
        elif name == "switch":
            self.toggle_dog()
        elif name == "proactive":
            self.active = not self.active; self.save()
        elif name == "topmost":
            self.topmost = not self.topmost; self.apply_topmost(); self.save()
        elif name == "slider" and value is not None:
            self.resize(round(BASE_SIZE * value))
            for popup in (self.glass_menu, self.glass_actions):
                if popup is not None and popup.win.winfo_exists():
                    popup.redraw()
        elif name == "reset":
            self.resize(BASE_SIZE)
        elif name == "dock":
            self.dock()
        elif name == "exit":
            self.quit()

    def glass_menu_action(self, name, value):
        self.last_touch = time.monotonic()
        if name == "actions":
            self.open_glass_actions()
        elif name in ("wave", "pet_head", "look", "work"):
            self.work_source = None
            self.touch("pet_front") if name == "pet_head" else self.show_pose(name)
        else:
            self.glass_common_action(name, value)

    def glass_actions_action(self, name, value):
        self.last_touch = time.monotonic()
        if name == "page":
            catalog = DOG if self.dog else NORMAL
            self.action_page = (self.action_page + 1) % ((len(catalog) + 10) // 11)
            if self.glass_actions is not None and self.glass_actions.win.winfo_exists():
                self.glass_actions.redraw()
        elif name.startswith("act:"):
            key = name[4:]
            self.work_source = None
            self.show_pose(key)
        else:
            self.glass_common_action(name, value)

    def glass_tray_action(self, name, value):
        self.last_touch = time.monotonic()
        if name == "show":
            self.close_panels(); self.root.deiconify()
        elif name == "panel":
            self.root.deiconify(); self.open_glass_menu()
        elif name == "hide":
            self.close_panels(); self.bubble_card.hide(); self.root.withdraw()
        else:
            self.glass_common_action(name, value)

    def resize(self, size):
        size = max(MIN_SIZE, min(MAX_SIZE, int(size)))
        if size == self.size:
            return
        self.size = size
        self.canvas.configure(width=size, height=size)
        self.canvas.coords(self.image_id, size // 2, size // 2)
        x, y = clamp_pet_position(self.root.winfo_x(), self.root.winfo_y(), (size, size), virtual_screen_bounds())
        self.root.geometry(f"{size}x{size}+{x}+{y}")
        remaining = 0 if self.pose_until == float("inf") else max(.1, self.pose_until - time.monotonic())
        self.show_pose(self.pose, seconds=remaining, words="")
        if self.bubble_card.visible and self.bubble_card.content is not None:
            words = self.bubble_card.content[0]
            self.bubble_card.show(words, (x, y, x + size, y + size),
                                  monitor_work_area(self.root.winfo_id()), size / BASE_SIZE, self.dog)
        self.save()

    def close_panels(self):
        for attr in ("glass_menu", "glass_actions", "glass_tray"):
            popup = getattr(self, attr)
            if popup is not None:
                popup.close()
            setattr(self, attr, None)

    def apply_topmost(self):
        self.root.attributes("-topmost", self.topmost)
        if self.bubble_card.win.winfo_exists():
            self.bubble_card.win.attributes("-topmost", self.topmost)
        for popup in (self.glass_menu, self.glass_actions, self.glass_tray):
            if popup is not None and popup.win.winfo_exists():
                popup.win.attributes("-topmost", self.topmost)

    @staticmethod
    def frame_interval(key):
        return 1.0 / PACK.action(key)["fps"]


    @staticmethod
    def screen_cursor():
        point = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        return point.x, point.y

    def over_own_window(self, mx, my):
        windows = (self.root, self.bubble_card.win,
                   *(popup.win for popup in (self.glass_menu, self.glass_actions,
                                               self.glass_tray) if popup is not None))
        for win in windows:
            if win.winfo_exists() and win.state() != "withdrawn":
                x, y = win.winfo_rootx(), win.winfo_rooty()
                if x <= mx < x + win.winfo_width() and y <= my < y + win.winfo_height():
                    return True
        return False

    def point_gaze(self, mx, my, now):
        cx = self.root.winfo_rootx() + self.size / 2
        cy = self.root.winfo_rooty() + self.size * 300 / 512
        dx, dy = mx - cx, my - cy
        if math.hypot(dx, dy) > 20:
            self.look_index = direction_index(dx, dy)
            self.look_until = now + .18

    def sample_pointer_activity(self, now):
        user32 = ctypes.windll.user32
        left_down = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
        mx, my = self.screen_cursor()
        if self.pose == "look" and self.press is None:
            self.point_gaze(mx, my, now)
        if self.press is not None and not self.dragged and now - self.press_started >= .25:
            self.point_gaze(mx, my, now)
        if left_down and not self.last_left_down and self.press is None:
            self.external_drag_origin = None if self.over_own_window(mx, my) else (mx, my)
        if not left_down:
            self.external_drag_origin = None
            if self.press is None and self.pose != "look":
                self.look_until = 0.0
        elif self.external_drag_origin is not None and self.press is None:
            ox, oy = self.external_drag_origin
            if math.hypot(mx - ox, my - oy) >= 7 and self.root.state() != "withdrawn":
                if self.pose != "idle":
                    self.work_source = None
                    self.show_pose("idle", seconds=0, words="")
                self.point_gaze(mx, my, now)
        self.last_left_down = left_down

    def sample_keyboard_activity(self, now):
        if now >= self.next_keyboard_sample:
            self.next_keyboard_sample = now + .12
            self.keyboard_active = self.keyboard_activity.poll(now) if PACK.interactions.get("keyboard", True) else False
        if not self.active or self.root.state() == "withdrawn":
            if self.work_source == "keyboard":
                self.work_source = None
                self.show_pose("idle", seconds=0, words="")
            return
        if self.press is not None or self.external_drag_origin is not None:
            return
        if self.work_source == "keyboard" and not self.keyboard_active:
            self.work_source = None
            self.show_pose("idle", seconds=0, words="")
        elif self.keyboard_active and self.work_source is None and self.pose == "idle":
            self.work_source = "keyboard"
            self.bubble_card.hide()
            self.show_pose("work", seconds=0, words="")

    def tick(self):
        now = time.monotonic()
        if now >= self.pose_until and self.press is None:
            self.show_pose("idle", seconds=0, words="")
        self.sample_pointer_activity(now) if PACK.interactions.get("mouse_gaze", True) else None
        self.sample_keyboard_activity(now)
        panels_open = any(popup is not None for popup in
                          (self.glass_menu, self.glass_actions, self.glass_tray))
        if PACK.ambient_actions and ambient_due(now, self.last_touch, self.last_ambient, enabled=self.active,
                       idle=self.pose == "idle" and self.press is None
                       and not self.keyboard_active and not panels_open,
                       visible=self.root.state() != "withdrawn"):
            self.last_ambient = now
            self.show_pose(random.choice(PACK.ambient_actions))
        pace = self.frame_interval(self.pose)
        if now - self.frame_last >= pace:
            self.frame = (self.frame + 1) % frame_count(self.pose)
            self.frame_last = now
        display = (("look_direction", self.look_index)
                   if "look_direction" in PACK.actions and (self.pose == "look" or
                   (self.pose == "idle" and now < self.look_until))
                   else (self.pose, self.frame))
        if display != self.display_key:
            self.photo = self.sprite(*display)
            self.display_key = display
            self.canvas.itemconfigure(self.image_id, image=self.photo)
        self.root.after(50, self.tick)

    def start_tray(self):
        if pystray is None:
            return
        with Image.open(PACK.frame_path("idle", 0)) as source:
            img = source.convert("RGBA")
        self.tray = TemplateTrayIcon("desktop_pet_" + PACK.id, img, APP_NAME,
            on_left=lambda: self.tray_queue.put("menu"),
            on_right=lambda: self.tray_queue.put("tray_menu"))
        self.tray.run_detached()


    def poll_tray(self):
        while not self.tray_queue.empty():
            action = self.tray_queue.get_nowait()
            if action == "menu":
                self.root.deiconify(); self.open_glass_menu()
            elif action == "tray_menu":
                self.open_glass_tray()
            elif action == "switch":
                self.toggle_dog()
            elif action == "quit":
                self.quit(); return
        self.root.after(150, self.poll_tray)

    def quit(self):
        self.cancel_pressed_cursor()
        self.save()
        if self.tray is not None:
            self.tray.stop()
        self.root.destroy()


def main():
    if "--self-test" in sys.argv:
        report = validate_resources()
        target = Path(sys.argv[sys.argv.index("--self-test") + 1]) if len(sys.argv) > sys.argv.index("--self-test") + 1 else CONFIG.with_name("self-test.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    mutex = acquire_instance()
    if os.name == "nt" and mutex is None:
        return
    try:
        DesktopPet().root.mainloop()
    except Exception:
        report = traceback.format_exc()
        try:
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            CONFIG.with_name("error.log").write_text(report, encoding="utf-8")
        except OSError:
            pass
        print(report, file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
