"""Xiaomou glass surfaces, ported from Xiaoan's proven panel layout.

All coordinates are logical pixels. The renderer is also usable without Tk, so
the installed UI can be compared with the HTML reference in a static QA pass.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

from PIL import ImageColor, Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageGrab


ASSETS = Path(__file__).resolve().parent / "assets"
from character_pack import selected_pack
PACK = selected_pack()
FONT_PATH = PACK.font_path or ASSETS / "Xiaolai-Regular.ttf"
BLUE = tuple(ImageColor.getrgb(PACK.theme.get("accent", "#AB7736")))
INK = tuple(ImageColor.getrgb(PACK.theme.get("ink", "#624528")))
MUTED = tuple(ImageColor.getrgb(PACK.theme.get("muted", "#8D6D44")))
PANEL_KEY = "#ff00fe"


@lru_cache(maxsize=96)
def continuous_corner_mask(size: tuple[int, int], bounds: tuple[int, int, int, int],
                           radius: int, samples: int = 4) -> Image.Image:
    """Antialiased continuous-curvature rounded rectangle (superellipse-like).

    This is an approximation of the continuous style, not Apple's private path.
    Supersampling keeps each edge pixel a real coverage value from 0 to 255.
    """
    w, h = size
    x1, y1, x2, y2 = bounds
    r = min(radius, (x2-x1)//2, (y2-y1)//2)
    p = 2/3.6
    corners = ((x2-r, y1+r, -math.pi/2, 0),
               (x2-r, y2-r, 0, math.pi/2),
               (x1+r, y2-r, math.pi/2, math.pi),
               (x1+r, y1+r, math.pi, 3*math.pi/2))
    points = []
    for cx, cy, a0, a1 in corners:
        for i in range(33):
            a = a0 + (a1-a0)*i/32
            ca, sa = math.cos(a), math.sin(a)
            px = cx + r*math.copysign(abs(ca)**p, ca)
            py = cy + r*math.copysign(abs(sa)**p, sa)
            points.append((round(px*samples), round(py*samples)))
    large = Image.new("L", (w*samples, h*samples), 0)
    ImageDraw.Draw(large).polygon(points, fill=255)
    return large.resize((w, h), Image.Resampling.LANCZOS)


def compose_on_backdrop(image: Image.Image, backdrop: Image.Image | None) -> Image.Image:
    """Flatten antialiased alpha against the actual desktop sample for Tk."""
    base = (backdrop.resize(image.size).convert("RGBA") if backdrop is not None
            else Image.new("RGBA", image.size, (245, 227, 190, 255)))
    return Image.alpha_composite(base, image.convert("RGBA")).convert("RGB")


def window_bitmap(image: Image.Image, backdrop: Image.Image | None,
                  key: str = PANEL_KEY) -> Image.Image:
    """Draw the glass over its sample, but leave the window exterior transparent.

    Windows/Tk only supports a binary color key here. Use the artwork's actual
    alpha as the window silhouette, including speech tails, so the clipping
    edge cannot drift away from the painted continuous corner. Pixels outside
    it are the *exact* key color and show the live desktop underneath.
    """
    from PIL import ImageColor

    result = compose_on_backdrop(image, backdrop)
    silhouette = image.getchannel("A").point(lambda alpha: 255 if alpha >= 128 else 0)
    outside = Image.new("RGB", image.size, ImageColor.getrgb(key))
    outside.paste(result, (0, 0), silhouette)
    result = outside
    return result


def font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FONT_PATH), size)
    except OSError:
        return ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", size)


def capture_backdrop(box: tuple[int, int, int, int],
                     exclude_window: int | None = None) -> Image.Image | None:
    """Sample the desktop, optionally excluding a visible owned popup.

    Display affinity excludes the popup from the capture without hiding it on
    the user's screen. If Windows cannot exclude it, refuse the live sample so
    we never paint a recursive copy of the popup into its own glass material.
    """
    hwnd = None
    excluded = False
    previous = wintypes.DWORD(0)
    try:
        if exclude_window is not None:
            user32 = ctypes.windll.user32
            user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
            user32.GetAncestor.restype = wintypes.HWND
            user32.GetWindowDisplayAffinity.argtypes = (wintypes.HWND,
                                                        ctypes.POINTER(wintypes.DWORD))
            user32.SetWindowDisplayAffinity.argtypes = (wintypes.HWND, wintypes.DWORD)
            hwnd = user32.GetAncestor(exclude_window, 2)  # GA_ROOT
            if not hwnd or not user32.GetWindowDisplayAffinity(hwnd, ctypes.byref(previous)):
                return None
            if not user32.SetWindowDisplayAffinity(hwnd, 0x11):  # WDA_EXCLUDEFROMCAPTURE
                return None
            excluded = True
        # Wait for DWM to apply the capture exclusion / finish hiding a popup.
        try:
            ctypes.windll.dwmapi.DwmFlush()
        except (AttributeError, OSError):
            pass
        return ImageGrab.grab(bbox=box, all_screens=True).convert("RGB")
    except (AttributeError, OSError, ValueError):
        return None
    finally:
        if excluded:
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, previous.value)


@dataclass(frozen=True)
class Hit:
    name: str
    box: tuple[int, int, int, int]
    label: str = ""

    def contains(self, x: int, y: int) -> bool:
        x1, y1, x2, y2 = self.box
        return x1 <= x < x2 and y1 <= y < y2


class GlassArtwork:
    """Draw a real blurred desktop sample under an optically tinted card."""

    def __init__(self, kind: str, size: tuple[int, int], avatar: Image.Image,
                 backdrop: Image.Image | None = None):
        self.kind, self.width, self.height = kind, *size
        self.avatar = avatar.convert("RGBA")
        self.backdrop = backdrop
        self.hits: list[Hit] = []
        self._fonts: dict[int, ImageFont.FreeTypeFont] = {}

    def _font(self, size: int) -> ImageFont.FreeTypeFont:
        if size not in self._fonts:
            self._fonts[size] = font(size)
        return self._fonts[size]

    def _base(self) -> Image.Image:
        w, h = self.width, self.height
        if self.backdrop is not None:
            source = self.backdrop.resize((w, h)).filter(ImageFilter.GaussianBlur(20))
            source = ImageEnhance.Color(source).enhance(1.15).convert("RGBA")
        else:
            source = Image.new("RGBA", (w, h), (*ImageColor.getrgb(PACK.theme.get("surface", "#E8CC97")), 255))
        wash = Image.new("RGBA", (w, h))
        wd = ImageDraw.Draw(wash)
        for y in range(h):
            t = y / max(1, h - 1)
            tint = ImageColor.getrgb(PACK.theme.get("surface", "#E8CC97"))
            wash_rgb = tuple(round(255 * (.78 - .20*t) + c * (.22 + .20*t)) for c in tint)
            wd.line((0, y, w, y), fill=(*wash_rgb, round(182-21*t)))
        material = Image.alpha_composite(source, wash)
        mask = continuous_corner_mask((w, h), (5, 5, w-6, h-6), 30)
        material.putalpha(mask)
        panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        shadow = Image.new("RGBA", (w, h), (100, 68, 34, 0))
        shadow.putalpha(mask.filter(ImageFilter.GaussianBlur(4)).point(
            lambda alpha: round(alpha*.18)))
        panel.alpha_composite(shadow)
        panel.alpha_composite(material)
        inner = continuous_corner_mask((w, h), (7, 7, w-8, h-8), 28)
        rim = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        rim.putalpha(ImageChops.subtract(mask, inner).point(
            lambda alpha: round(alpha*.86)))
        panel.alpha_composite(rim)
        return panel

    def _text(self, image: Image.Image, xy: tuple[int, int], value: str,
              size: int, fill=INK, anchor="lm") -> None:
        value = value.replace("小哞", PACK.name)
        ImageDraw.Draw(image).text(xy, value, font=self._font(size),
                                   fill=fill, anchor=anchor, stroke_width=0)

    def _line(self, image: Image.Image, y: int, x1=25, x2=None) -> None:
        if x2 is None:
            x2 = self.width - 25
        # Drawing a low-alpha color directly onto an RGBA panel replaces its
        # alpha, creating a real transparent slit through the window.
        ImageDraw.Draw(image).line((x1, y, x2, y), fill=(215, 181, 130, 255), width=1)

    def _header(self, im: Image.Image, title: str, sub: str) -> None:
        w = self.width
        avatar = self.avatar.copy()
        avatar.thumbnail((58, 62), Image.Resampling.LANCZOS)
        ax = 26 + (58-avatar.width)//2
        im.alpha_composite(avatar, (ax, 17))
        self._text(im, (95, 40), title, 23)
        self._text(im, (95, 65), sub, 12, MUTED)
        self._text(im, (w-27, 81), "拖动标题可移动", 10, MUTED, "rm")
        self._button(im, (w-57, 25, w-23, 59), "×", "close", size=19, mode="quiet")

    def _button(self, im: Image.Image, box: tuple[int, int, int, int],
                label: str, name: str, *, size=17, mode="normal",
                hover: str | None = None, pressed: str | None = None,
                pointer: tuple[int, int] | None = None, align="center") -> None:
        x1, y1, x2, y2 = box
        w, h = x2-x1, y2-y1
        active, down = hover == name, pressed == name
        tile = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        td = ImageDraw.Draw(tile)
        radius = min(18, h//2-2)
        if mode == "primary":
            top, bottom = ((*BLUE, 236), (*BLUE, 243))
            text_color = (255, 255, 255)
        elif mode == "quiet":
            top, bottom = ((255, 253, 244, 180), (247, 226, 185, 145))
            text_color = INK
        else:
            top, bottom = ((255, 253, 244, 224), (246, 226, 185, 175))
            text_color = (153, 66, 80) if mode == "danger" else INK
        if active and mode != "primary":
            top = (255, 255, 255, 229)
            bottom = (249, 226, 169, 187)
        if down:
            top = tuple(max(0, c-12) for c in top[:3]) + (top[3],)
            bottom = tuple(max(0, c-8) for c in bottom[:3]) + (bottom[3],)
        # A translucent gradient lets the blurred backdrop remain visible.
        grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        for yy in range(h):
            t = yy/max(1, h-1)
            gd.line((0, yy, w, yy), fill=tuple(round(top[i]*(1-t)+bottom[i]*t) for i in range(4)))
        m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m).rounded_rectangle((1, 1, w-2, h-2), radius=radius, fill=255)
        grad.putalpha(Image.composite(grad.getchannel("A"), Image.new("L", (w, h)), m))
        tile.alpha_composite(grad)
        if active and pointer:
            px, py = pointer[0]-x1, pointer[1]-y1
            glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ImageDraw.Draw(glow).ellipse((px-46, py-29, px+46, py+29),
                                         fill=(255, 255, 255, 69))
            glow = glow.filter(ImageFilter.GaussianBlur(16))
            glow.putalpha(Image.composite(glow.getchannel("A"),
                                          Image.new("L", (w, h)), m))
            tile.alpha_composite(glow)
        td = ImageDraw.Draw(tile)
        td.rounded_rectangle((1, 1, w-2, h-2), radius=radius,
                             outline=(255, 255, 255, 238 if active else 204), width=2)
        im.alpha_composite(tile, (x1, y1))
        tx = x1+17 if align == "left" else (x1+x2)//2
        self._text(im, (tx, (y1+y2)//2-1), label, size, text_color,
                   "lm" if align == "left" else "mm")
        self.hits.append(Hit(name, box, label))

    def _setting(self, im: Image.Image, y: int, title: str, sub: str,
                 name: str, enabled: bool, **effects) -> None:
        self._text(im, (26, y+14), title, 16)
        self._text(im, (26, y+33), sub, 11, MUTED)
        x1, x2 = self.width-76, self.width-27
        d = ImageDraw.Draw(im)
        color = (*BLUE, 255) if enabled else (211, 187, 147, 255)
        d.rounded_rectangle((x1, y+11, x2, y+40), radius=15,
                            fill=color, outline=(255, 255, 255, 255), width=1)
        cx = x2-15 if enabled else x1+15
        d.ellipse((cx-10, y+15, cx+10, y+35), fill=(255, 255, 255, 255))
        self.hits.append(Hit(name, (20, y+4, self.width-20, y+47), title))
        self._line(im, y+51)

    def _slider(self, im: Image.Image, y: int, scale: float) -> None:
        self._text(im, (26, y), "小哞的大小", 16)
        self._text(im, (self.width-26, y), f"{round(scale*100)}%", 16, BLUE, "rm")
        x1, x2 = 27, self.width-27
        cy = y+34
        fill_x = round(x1+(x2-x1)*(scale-.65))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((x1, cy-3, x2, cy+3), radius=3,
                            fill=(255, 253, 245, 255))
        d.rounded_rectangle((x1, cy-3, fill_x, cy+3), radius=3,
                            fill=(*BLUE, 255))
        d.ellipse((fill_x-9, cy-9, fill_x+9, cy+9),
                  fill=(255, 247, 224, 255), outline=(*BLUE, 255), width=2)
        self.hits.append(Hit("slider", (x1-9, cy-13, x2+9, cy+14), "小哞的大小"))

    def render(self, *, scale=1.0, proactive=True, topmost=True, dog=False,
               actions=(), page=0,
               hover: str | None = None, pressed: str | None = None,
               pointer: tuple[int, int] | None = None) -> Image.Image:
        self.hits.clear()
        im = self._base()
        fx = dict(hover=hover, pressed=pressed, pointer=pointer)
        if self.kind == "menu":
            self._header(im, PACK.name + "在这里", PACK.message("subtitle", "陪我玩一会儿吧"))
            self._text(im, (26, 109), "现在想做什么", 12, MUTED)
            labels = [("招招手", "wave"), ("摸摸头", "pet_head"),
                      ("看看你", "look"), ("陪你工作", "work")]
            for i, (label, name) in enumerate(labels):
                col, row = i%2, i//2
                x, y = 25+col*190, 128+row*60
                self._button(im, (x, y, x+180, y+52), label, name, size=19, **fx)
            self._text(im, (26, 258), "更多陪伴", 12, MUTED)
            self._button(im, (25, 277, 205, 325), "全部动作 ›", "actions", size=16, **fx)
            self._button(im, (215, 277, 395, 325), "说说话 ›", "chat", size=16, **fx)
            self._button(im, (25, 335, 395, 387), "选择角色包 ›", "switch",
                         mode="primary", size=16, **fx)
            self._line(im, 402)
            self._setting(im, 411, "主动陪伴", "偶尔主动和你说说话", "proactive", proactive)
            self._setting(im, 467, "保持置顶", "小哞一直留在桌面上", "topmost", topmost)
            self._slider(im, 550, scale)
            self._button(im, (25, 612, 149, 653), "重置大小", "reset", size=14, **fx)
            self._button(im, (156, 612, 312, 653), "停靠右下角", "dock", size=14, **fx)
            self._button(im, (319, 612, 395, 653), "退出", "exit", size=14,
                         mode="danger", **fx)
        elif self.kind == "tray":
            self._header(im, PACK.name + "在这里", "桌面陪伴与互动")
            for i, (label, name) in enumerate([
                ("显示小哞", "show"), ("打开互动面板", "panel"),
                ("和小哞说说话", "chat"),
                ("选择角色包", "switch"),
                ("停靠右下角", "dock"), ("暂时隐藏小哞", "hide"),
                ("退出小哞", "exit")]):
                y = 94+i*53+(8 if i>=4 else 0)
                if i == 4:
                    self._line(im, y-5)
                self._button(im, (22, y, self.width-22, y+47), label, name,
                             size=16, mode="primary" if i==0 else "danger" if i==6 else "normal",
                             align="left", **fx)
        elif self.kind == "actions":
            self._header(im, PACK.name + "的动作", "选一个喜欢的表情和动作")
            pages = max(1, math.ceil(len(actions)/11))
            self._text(im, (26, 103), f"轻松相处 · {page+1}/{pages} 页", 12, MUTED)
            if pages > 1:
                self._button(im, (302, 91, 395, 119), "下一页 ›" if page+1 < pages else "第一页 ›",
                             "page", size=12, mode="quiet", **fx)
            choices = actions[page*11:page*11+10]
            for i, (name, label) in enumerate(choices):
                col, row = i%2, i//2
                x, y = 24+col*191, 123+row*61
                self._button(im, (x, y, x+182, y+53), label, f"act:{name}", size=18, **fx)
            wide_index = page*11+10
            if wide_index < len(actions):
                name, label = actions[wide_index]
                self._button(im, (24, 428, self.width-24, 482), label,
                             f"act:{name}", size=18, **fx)
            else:
                self._button(im, (24, 428, self.width-24, 482), "返回第一页 ›",
                             "page", size=18, **fx)
            self._text(im, (26, 508), "小哞的大小", 12, MUTED)
            self._slider(im, 541, scale)
            self._text(im, (26, 603), "选中动作后，小哞会在桌面回应你。", 12, MUTED)
            self._button(im, (24, 641, self.width-24, 693), "和小哞说说话 ›", "chat",
                         size=17, mode="primary", **fx)
        return im

    def hit(self, x: int, y: int) -> Hit | None:
        return next((h for h in reversed(self.hits) if h.contains(x, y)), None)
