"""Validate a draft character pack without executing pack-supplied code."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from PIL import Image, UnidentifiedImageError


def validate(root: Path, *, check_files: bool = True) -> dict:
    root = root.resolve()
    errors, warnings = [], []
    try:
        doc = json.loads((root / "character.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [f"character.json: {exc}"], "warnings": []}
    if not isinstance(doc, dict):
        return {"ok": False, "errors": ["character.json must contain an object"], "warnings": []}
    if type(doc.get("schema_version")) is not int or doc.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not isinstance(doc.get("id"), str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", doc["id"]):
        errors.append("id must contain lowercase letters, numbers and hyphens")
    if not isinstance(doc.get("name"), str) or not doc["name"].strip() or len(doc["name"]) > 24:
        errors.append("name must be a nonempty string up to 24 characters")
    canvas = doc.get("canvas")
    if not (isinstance(canvas, list) and len(canvas) == 2 and all(type(n) is int and 0 < n <= 4096 for n in canvas)):
        errors.append("canvas must be two integers in 1..4096")
        canvas = None
    theme = doc.get("theme")
    if not isinstance(theme, dict) or not isinstance(theme.get("accent"), str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", theme["accent"]):
        errors.append("theme.accent must be a #RRGGBB color")

    def path_in_pack(value):
        if not isinstance(value, str) or not value or Path(value).is_absolute():
            raise ValueError("expected a relative path")
        path = (root / value).resolve()
        if not path.is_relative_to(root):
            raise ValueError("path escapes character pack")
        return path

    if isinstance(theme, dict) and theme.get("font") is not None:
        try:
            font_path = path_in_pack(theme["font"])
            if check_files and not font_path.is_file():
                errors.append("theme.font file not found")
            elif check_files:
                from PIL import ImageFont
                ImageFont.truetype(str(font_path),16)
        except (ValueError, OSError) as exc:
            errors.append(f"theme.font: {exc}")
    actions = doc.get("actions")
    if not isinstance(actions, dict) or "idle" not in actions:
        errors.append("actions must contain idle")
        actions = actions if isinstance(actions, dict) else {}
    for color in ("ink", "muted", "surface"):
        if isinstance(theme, dict) and color in theme and (not isinstance(theme[color], str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", theme[color])):
            errors.append(f"theme.{color} must be a #RRGGBB color")
    aliases = doc.get("aliases", {})
    if not isinstance(aliases, dict) or any(not isinstance(k,str) or not isinstance(v,str) or v not in actions for k,v in aliases.items()):
        errors.append("aliases must map action names to existing actions")
        aliases = {}
    zones = doc.get("hotzones", [])
    if not isinstance(zones, list):
        errors.append("hotzones must be a list")
        zones = []
    for region in zones:
        if not isinstance(region,dict):
            errors.append("hotzone must be an object")
            continue
        rect = region.get("rect")
        if not (isinstance(rect,list) and len(rect)==4 and all(type(n) is int and 0<=n<=512 for n in rect) and rect[0]<rect[2] and rect[1]<rect[3]):
            errors.append("hotzone rect must be [left,top,right,bottom] within 0..512")
        action = region.get("action")
        if not isinstance(action,str) or action not in actions:
            errors.append("hotzone action must exist")
    interactions = doc.get("interactions", {})
    if not isinstance(interactions,dict):
        errors.append("interactions must be an object")
        interactions = {}
    for event in ("click", "double_click", "hold"):
        value = interactions.get(event)
        if event in interactions and (not isinstance(value,str) or value not in actions):
            errors.append(f"interactions.{event} must reference an existing action")
    for event in ("keyboard", "mouse_gaze"):
        if event in interactions and type(interactions[event]) is not bool:
            errors.append(f"interactions.{event} must be boolean")
    ambient = interactions.get("ambient", [])
    if not isinstance(ambient,list) or any(not isinstance(k,str) or k not in actions for k in ambient):
        errors.append("interactions.ambient must list existing actions")
    messages = doc.get("messages", {})
    if not isinstance(messages,dict) or any(not isinstance(v,str) for v in messages.values()):
        errors.append("messages must be an object of strings")
    checked = 0
    cursors = doc.get("cursors", {})
    if not isinstance(cursors,dict):
        errors.append("cursors must be an object")
        cursors = {}
    for key,value in cursors.items():
        try:
            path = path_in_pack(value)
            if key not in ("head", "head_pressed", "body") or path.suffix.lower() != ".cur" or (check_files and not path.is_file()):
                errors.append(f"cursors.{key} must name an existing .cur file")
        except (ValueError,OSError) as exc:
            errors.append(f"cursors.{key}: {exc}")
    for name, action in actions.items():
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", name) or not isinstance(action, dict):
            errors.append(f"invalid action: {name}")
            continue
        if "label" in action and (not isinstance(action["label"],str) or len(action["label"])>24):
            errors.append(f"{name}: label must be a string up to 24 characters")
        frames = action.get("frames")
        if not isinstance(frames, list) or not frames:
            errors.append(f"{name}: frames must be a nonempty list")
            continue
        fps = action.get("fps")
        if type(fps) not in (int, float) or not 0 < fps <= 60:
            errors.append(f"{name}: fps must be in (0, 60]")
        lines = action.get("dialogue", [])
        if not isinstance(lines, list) or any(not isinstance(s, str) or not s.strip() for s in lines):
            errors.append(f"{name}: dialogue must be a list of nonempty strings")
        if name == "look_direction" and len(frames) != 16:
            errors.append("look_direction must contain exactly 16 direction frames")
        elif name != "look_direction" and len(frames) < 5:
            warnings.append(f"{name}: fewer than 5 frames")
        for frame in frames:
            try:
                path = path_in_pack(frame)
                if path.suffix.lower() != ".png":
                    raise ValueError("expected PNG")
                if not check_files:
                    continue
                with Image.open(path) as image:
                    if image.format != "PNG" or image.mode != "RGBA":
                        errors.append(f"{name}/{frame}: expected RGBA PNG")
                    if canvas and image.size != tuple(canvas):
                        errors.append(f"{name}/{frame}: incorrect dimensions {image.size}")
                    if image.mode == "RGBA" and image.getchannel("A").getbbox() is None:
                        errors.append(f"{name}/{frame}: fully transparent")
                    image.load()
                checked += 1
            except (ValueError, OSError, UnidentifiedImageError) as exc:
                errors.append(f"{name}/{frame}: {exc}")
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "frames_checked": checked, "manual_review_required": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=Path)
    args = parser.parse_args()
    report = validate(args.pack)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
