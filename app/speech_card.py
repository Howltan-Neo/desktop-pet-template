"""Warm speech card with the same sizing and placement rules as Xiaoan."""
from __future__ import annotations

import tkinter as tk

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageTk

from glass_ui import PACK, INK, BLUE, capture_backdrop, continuous_corner_mask, font, window_bitmap


KEY = "#010203"
def _lines(words: str, face: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    result: list[str] = []
    for paragraph in words.split("\n"):
        line = ""
        for char in paragraph:
            if line and face.getlength(line + char) > max_width:
                result.append(line)
                line = char
            else:
                line += char
        result.append(line)
    return result or [""]


def bubble_bitmap(width: int, height: int, tail: int, scale: float) -> Image.Image:
    size = (width, height + tail + 3)
    art = Image.new("RGBA", size)
    mask = continuous_corner_mask(size, (1, 1, width - 2, height - 2),
                                  max(12, round(17 * scale)))
    body = Image.new("RGBA", size, (255, 250, 235, 246))
    body.putalpha(mask.point(lambda value: round(value * 246 / 255)))
    art.alpha_composite(body)
    if tail:
        middle = width // 2
        point = Image.new("L", (width * 4, size[1] * 4))
        ImageDraw.Draw(point).polygon(
            [(4 * (middle - tail), 4 * (height - 3)),
             (4 * (middle + tail), 4 * (height - 3)),
             (4 * middle, 4 * (height + tail))], fill=255)
        point = point.resize(size, Image.Resampling.LANCZOS)
        tip = Image.new("RGBA", size, (255, 250, 235, 0))
        tip.putalpha(point.point(lambda value: round(value * 246 / 255)))
        art.alpha_composite(tip)
    inner = continuous_corner_mask(size, (3, 3, width - 4, height - 4),
                                   max(10, round(15 * scale)))
    rim = Image.new("RGBA", size, (255, 255, 255, 0))
    rim.putalpha(ImageChops.subtract(mask, inner).point(lambda value: round(value * .8)))
    art.alpha_composite(rim)
    return art


def speech_position(size: tuple[int, int], pet_box: tuple[int, int, int, int],
                    work_area: tuple[int, int, int, int], scale: float) -> tuple[int, int, str]:
    width, height = size
    x1, y1, x2, y2 = pet_box
    left, top, right, bottom = work_area
    margin = 4
    gap = max(8, round(12 * scale))
    if width > right - left - 2 * margin or height > bottom - top - 2 * margin:
        return left + margin, top + margin, "hidden"
    x = max(left + margin, min(right - width - margin,
                               round((x1 + x2 - width) / 2)))
    # The hair reaches the top of Xiaomou's transparent window. Position the
    # whole card outside that window rather than using an estimated hairline.
    y = y1 - gap - height
    if y >= top + margin:
        return x, y, "above"
    for side_x in (x2 + gap, x1 - gap - width):
        if left + margin <= side_x and side_x + width <= right - margin:
            side_y = max(top + margin, min(bottom - height - margin,
                                           y1 + round((y2 - y1 - height) / 2)))
            return side_x, side_y, "side"
    below = y2 + gap
    if below + height <= bottom - margin:
        return x, below, "below"
    return x, top + margin, "hidden"


class SpeechCard:
    def __init__(self, owner: tk.Misc):
        self.win = tk.Toplevel(owner)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.configure(bg=KEY)
        self.win.wm_attributes("-transparentcolor", KEY)
        self.win.wm_attributes("-topmost", bool(owner.wm_attributes("-topmost")))
        self.canvas = tk.Canvas(self.win, bg=KEY, bd=0, highlightthickness=0)
        self.canvas.pack()
        self.item = self.canvas.create_image(0, 0, anchor="nw")
        self.visible = False
        self.photo: ImageTk.PhotoImage | None = None
        self.art: Image.Image | None = None
        self.top_art: Image.Image | None = None
        self.side_art: Image.Image | None = None
        self.backdrop: Image.Image | None = None
        self.position: tuple[int, int] | None = None
        self.size = (0, 0)
        self.content: tuple[str, float, str, bool] | None = None
        self.refresh_timer: str | None = None

    @staticmethod
    def render(words: str, scale: float, tail: bool, dog: bool = False) -> Image.Image:
        ui_scale = .55 + .55 * scale
        body_font = font(max(16, round(18 * ui_scale)))
        label_font = font(max(12, round(12 * ui_scale)))
        padding = round(17 * ui_scale)
        max_width = round(350 * ui_scale)
        lines = _lines(words, body_font, max_width - 2 * padding)
        measured = max((body_font.getlength(line) for line in lines), default=0)
        width = round(min(max_width, max(270 * ui_scale, measured + 2 * padding)))
        line_height = round(25 * ui_scale)
        body_y = round(32 * ui_scale)
        height = body_y + len(lines) * line_height + round(13 * ui_scale)
        tail_size = max(6, round(8 * ui_scale)) if tail else 0
        art = bubble_bitmap(width, height, tail_size, ui_scale)
        draw = ImageDraw.Draw(art)
        draw.text((padding, round(9 * ui_scale)),
                  PACK.name + " · 对你说",
                  font=label_font, fill=(*BLUE, 255))
        for index, line in enumerate(lines):
            draw.text((padding, body_y + index * line_height), line,
                      font=body_font, fill=(*INK, 255))
        return art

    def hide(self) -> None:
        if self.refresh_timer is not None:
            self.win.after_cancel(self.refresh_timer)
            self.refresh_timer = None
        if self.visible:
            self.win.withdraw()
            self.visible = False

    def _draw(self) -> None:
        if self.art is not None:
            self.photo = ImageTk.PhotoImage(window_bitmap(self.art, self.backdrop, KEY),
                                             master=self.win)
            self.canvas.itemconfigure(self.item, image=self.photo)

    def _refresh(self) -> None:
        self.refresh_timer = None
        if self.position is None:
            return
        x, y = self.position
        backdrop = capture_backdrop((x, y, x + self.size[0], y + self.size[1]),
                                    exclude_window=self.win.winfo_id() if self.visible else None)
        if backdrop is not None:
            self.backdrop = backdrop
        if backdrop is not None or self.photo is None:
            self._draw()
        if self.visible:
            self.refresh_timer = self.win.after(1800, self._refresh)

    def show(self, words: str, pet_box: tuple[int, int, int, int],
             work_area: tuple[int, int, int, int], scale: float, dog: bool) -> None:
        if self.content is None or self.content[:2] != (words, scale) or self.content[3] != dog:
            self.top_art = self.render(words, scale, True, dog)
            self.side_art = self.render(words, scale, False, dog)
        assert self.top_art is not None and self.side_art is not None
        art = self.top_art
        x, y, placement = speech_position(art.size, pet_box, work_area, scale)
        if placement != "above":
            art = self.side_art
            x, y, placement = speech_position(art.size, pet_box, work_area, scale)
        if placement == "hidden":
            self.hide()
            return
        content = (words, scale, placement, dog)
        changed = content != self.content
        if changed:
            self.art, self.size, self.content = art, art.size, content
            self.canvas.configure(width=self.size[0], height=self.size[1])
        if (x, y) != self.position or changed:
            self.position = (x, y)
            self.win.geometry(f"{self.size[0]}x{self.size[1]}+{x}+{y}")
            if not self.visible or changed:
                if self.refresh_timer is not None:
                    self.win.after_cancel(self.refresh_timer)
                    self.refresh_timer = None
                self._refresh()
            else:
                if self.refresh_timer is not None:
                    self.win.after_cancel(self.refresh_timer)
                self.refresh_timer = self.win.after(160, self._refresh)
        if not self.visible:
            self.win.deiconify()
            self.win.lift()
            self.visible = True
            if self.refresh_timer is None:
                self.refresh_timer = self.win.after(1800, self._refresh)
