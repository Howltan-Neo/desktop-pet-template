"""Character data contract shared by the controller and artwork renderer."""
from __future__ import annotations
import json
import os
import random
import sys
from pathlib import Path
from functools import lru_cache


class Dialogue:
    def __init__(self, pack):
        self.pack, self.remaining = pack, {}

    def next(self, _variant, key, fallback=""):
        key = self.pack.resolve_action(key)
        lines = self.pack.action(key).get("dialogue", [])
        if not lines:
            return fallback
        if not self.remaining.get(key):
            self.remaining[key] = list(lines)
            random.shuffle(self.remaining[key])
        return self.remaining[key].pop()


class CharacterPack:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.data = json.loads((self.root / "character.json").read_text(encoding="utf-8"))
        self.id, self.name = self.data["id"], self.data["name"]
        self.actions, self.theme = self.data["actions"], self.data["theme"]
        self.interactions = self.data.get("interactions", {})
        self.hotzones = self.data.get("hotzones", [])
        self.aliases = self.data.get("aliases", {})
        self.ambient_actions = [key for key in self.interactions.get("ambient", []) if key in self.actions]
        self.font_path = self.path(self.theme["font"]) if self.theme.get("font") else None
        self.dialogue = Dialogue(self)
        self.settings_path = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "DesktopPetTemplate" / self.id / "settings.json"

    def path(self, value):
        path = (self.root / value).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Path escapes character pack")
        return path

    def resolve_action(self, key):
        if key == "look" and "look_direction" in self.actions:
            return "look"
        key = self.aliases.get(key, key)
        return key if key in self.actions else "idle"

    def action(self, key):
        if key == "look" and "look_direction" in self.actions:
            key = "look_direction"
        return self.actions[self.resolve_action(key)]

    def frame_path(self, key, index=0):
        action = self.action(key)
        return self.path(action["frames"][index % len(action["frames"])])

    def message(self, key, fallback=""):
        return self.data.get("messages", {}).get(key, fallback)


@lru_cache(maxsize=1)
def selected_pack():
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return CharacterPack(os.environ.get("DESKTOP_PET_PACK", str(base / "characters" / "xiaomou")))
