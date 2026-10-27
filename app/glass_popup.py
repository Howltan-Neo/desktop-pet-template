"""Tk bridge for the shared Pillow glass artwork."""
from __future__ import annotations

import time
import tkinter as tk
from typing import Callable

from PIL import Image, ImageTk

from glass_ui import GlassArtwork, PANEL_KEY, capture_backdrop, window_bitmap
from window_placement import virtual_screen_bounds


class GlassPopup:
    def __init__(self, owner: tk.Misc, kind: str, size: tuple[int, int],
                 position: tuple[int, int], avatar: Image.Image,
                 state: Callable[[], dict], action: Callable[[str, float | None], None],
                 on_close: Callable[[], None] | None = None,
                 on_move: Callable[[tuple[int, int]], None] | None = None,
                 work_area: tuple[int, int, int, int] | None = None):
        self.kind, self.width, self.height = kind, *size
        self.state, self.action, self.on_close = state, action, on_close
        self.on_move = on_move
        self.work_area = work_area or virtual_screen_bounds()
        self.x, self.y = position
        backdrop = capture_backdrop((self.x, self.y, self.x+self.width, self.y+self.height))
        self.art = GlassArtwork(kind, size, avatar, backdrop)
        self.win = tk.Toplevel(owner)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.configure(bg=PANEL_KEY)
        self.win.wm_attributes("-transparentcolor", PANEL_KEY)
        self.win.wm_attributes("-topmost", bool(owner.wm_attributes("-topmost")))
        self.win.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")
        self.canvas = tk.Canvas(self.win, width=self.width, height=self.height,
                                bg=PANEL_KEY, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.item = self.canvas.create_image(0, 0, anchor="nw")
        self.photo: ImageTk.PhotoImage | None = None
        self.hover: str | None = None
        self.pressed: str | None = None
        self.pointer: tuple[int, int] | None = None
        self.dragging_slider = False
        self.drag_origin: tuple[int, int, int, int] | None = None
        self.dragged = False
        self.repositioning = False
        self.last_draw = 0.0
        self.backdrop_timer: str | None = None
        self.redraw()
        self.canvas.bind("<Motion>", self._motion)
        self.canvas.bind("<Leave>", self._leave)
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.win.bind("<Escape>", lambda _event: self.close())
        self.win.bind("<Tab>", self._tab)
        self.win.bind("<Return>", self._activate)
        self.win.bind("<space>", self._activate)
        for sequence, dx, dy in (("<Alt-Left>", -10, 0),
                                 ("<Alt-Right>", 10, 0),
                                 ("<Alt-Up>", 0, -10),
                                 ("<Alt-Down>", 0, 10)):
            self.win.bind(sequence, lambda _e, a=dx, b=dy: self._nudge(a, b))
        self.win.deiconify()
        self.win.focus_force()
        self.backdrop_timer = self.win.after(1800, self._refresh_backdrop)

    def redraw(self) -> None:
        if not self.win.winfo_exists():
            return
        image = self.art.render(**self.state(), hover=self.hover,
                                pressed=self.pressed, pointer=self.pointer)
        self.photo = ImageTk.PhotoImage(window_bitmap(image, self.art.backdrop), master=self.win)
        self.canvas.itemconfigure(self.item, image=self.photo)
        self.last_draw = time.monotonic()

    def _refresh_backdrop(self) -> None:
        self.backdrop_timer = None
        if not self.win.winfo_exists():
            return
        if not self.repositioning and self.drag_origin is None:
            backdrop = capture_backdrop((self.x, self.y,
                                         self.x+self.width, self.y+self.height),
                                        exclude_window=self.win.winfo_id())
            if backdrop is not None:
                self.art.backdrop = backdrop
                self.redraw()
        self.backdrop_timer = self.win.after(1800, self._refresh_backdrop)

    def reposition(self, position: tuple[int, int]) -> None:
        self.repositioning = True
        self.win.withdraw()
        self.x, self.y = position
        self.win.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")
        self.win.update_idletasks()
        # The sampled desktop must correspond to the card's new position.
        self.art.backdrop = capture_backdrop((self.x, self.y,
                                              self.x+self.width, self.y+self.height))
        self.redraw()
        self.win.deiconify()
        self.win.focus_force()
        self.win.after(220, lambda: setattr(self, "repositioning", False))

    def _clamp(self, x: int, y: int) -> tuple[int, int]:
        left, top, right, bottom = self.work_area
        return (max(left+4, min(right-self.width-4, x)),
                max(top+4, min(bottom-self.height-4, y)))

    def _nudge(self, dx: int, dy: int) -> str:
        pos = self._clamp(self.x+dx, self.y+dy)
        if pos != (self.x, self.y):
            self.reposition(pos)
            if self.on_move:
                self.on_move(pos)
        return "break"

    def _motion(self, event: tk.Event) -> None:
        hit = self.art.hit(event.x, event.y)
        name = hit.name if hit else None
        cursor = "hand2" if hit else "fleur" if 8 <= event.y < 90 else "arrow"
        try:
            self.canvas.configure(cursor=cursor)
        except tk.TclError:
            self.canvas.configure(cursor="hand2" if cursor == "fleur" else "arrow")
        self.pointer = (event.x, event.y)
        if name != self.hover or (name and time.monotonic()-self.last_draw > .055):
            self.hover = name
            self.redraw()

    def _leave(self, _event: tk.Event) -> None:
        self.hover = None
        self.pointer = None
        self.redraw()

    def _press(self, event: tk.Event) -> None:
        hit = self.art.hit(event.x, event.y)
        if hit is None and 8 <= event.y < 90:
            self.drag_origin = (event.x_root, event.y_root, self.x, self.y)
            self.dragged = False
            return
        self.pressed = hit.name if hit else None
        self.dragging_slider = self.pressed == "slider"
        if self.dragging_slider:
            self._slider_value(event.x)
        self.redraw()

    def _drag(self, event: tk.Event) -> None:
        if self.drag_origin is not None:
            px, py, x, y = self.drag_origin
            dx, dy = event.x_root-px, event.y_root-py
            if not self.dragged and abs(dx)+abs(dy) < 5:
                return
            self.dragged = True
            nx, ny = self._clamp(x+dx, y+dy)
            self.x, self.y = nx, ny
            self.win.geometry(f"+{nx}+{ny}")
            return
        if self.dragging_slider:
            self._slider_value(event.x)
        else:
            self._motion(event)

    def _release(self, event: tk.Event) -> None:
        if self.drag_origin is not None:
            self.drag_origin = None
            if self.dragged:
                self.dragged = False
                pos = (self.x, self.y)
                self.reposition(pos)
                if self.on_move:
                    self.on_move(pos)
            return
        hit = self.art.hit(event.x, event.y)
        name = self.pressed
        self.pressed = None
        self.dragging_slider = False
        if name == "slider":
            self.action("slider_commit", None)
        if name and hit and hit.name == name and name != "slider":
            self.action(name, None)
        if self.win.winfo_exists():
            self.redraw()

    def _slider_value(self, x: int) -> None:
        start, end = 27, self.width-27
        value = .65+min(1.0, max(0.0, (x-start)/(end-start)))
        self.action("slider", value)

    def _tab(self, _event: tk.Event) -> str:
        names = [hit.name for hit in self.art.hits]
        if names:
            index = names.index(self.hover) if self.hover in names else -1
            self.hover = names[(index+1) % len(names)]
            self.redraw()
        return "break"

    def _activate(self, _event: tk.Event) -> str:
        if self.hover and self.hover != "slider":
            self.action(self.hover, None)
        return "break"

    def _focus_out(self, _event: tk.Event) -> None:
        def check() -> None:
            if not self.win.winfo_exists() or self.repositioning or self.drag_origin is not None:
                return
            px, py = self.win.winfo_pointerxy()
            inside = self.x <= px < self.x+self.width and self.y <= py < self.y+self.height
            if self.win.focus_displayof() is None and not inside:
                self.close()
        self.win.after(150, check)

    def close(self) -> None:
        if self.win.winfo_exists():
            if self.backdrop_timer is not None:
                self.win.after_cancel(self.backdrop_timer)
                self.backdrop_timer = None
            self.win.destroy()
        if self.on_close:
            self.on_close()
