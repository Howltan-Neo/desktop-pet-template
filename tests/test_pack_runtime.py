import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "app"))
from character_pack import CharacterPack
from keyboard_activity import KeyboardActivity
from activity_logic import direction_index, ambient_due
from pack_validation import validate

ROOT = Path(__file__).resolve().parents[1]


class RuntimeTests(unittest.TestCase):
    def test_all_migrated_frames_load(self):
        from PIL import Image
        for folder in sorted((ROOT / "characters").iterdir()):
            if not (folder / "character.json").exists():
                continue
            with self.subTest(pack=folder.name):
                result = validate(folder)
                self.assertTrue(result["ok"],result["errors"])
                pack = CharacterPack(folder)
                for key,action in pack.actions.items():
                    self.assertGreater(len(action["frames"]),0)
                    for i in range(len(action["frames"])):
                        with Image.open(pack.frame_path(key,i)) as frame:
                            self.assertEqual(frame.size,tuple(pack.data["canvas"]))
                self.assertEqual(pack.frame_path("unknown"),pack.frame_path("idle"))

    def test_xiaoan_alias_and_dialogue_no_repeat_in_cycle(self):
        pack = CharacterPack(ROOT / "characters/xiaoan")
        from PIL import Image
        with Image.open(pack.frame_path("idle")) as image:
            bounds = image.getchannel("A").getbbox()
            self.assertGreater(bounds[3]-bounds[1],400,"Migration must scale up atlas cells to fill the shared canvas")
        self.assertEqual(pack.resolve_action("pet_left"),"pet_front")
        self.assertEqual(pack.frame_path("look",7),pack.frame_path("look_direction",7))
        count = len(pack.action("wave")["dialogue"])
        lines = [pack.dialogue.next("", "wave") for _ in range(count)]
        self.assertEqual(len(set(lines)),count)

    def test_keyboard_counts_only_and_expires(self):
        state = {}
        keyboard = KeyboardActivity(key_state=lambda key: state.get(key,0))
        self.assertFalse(keyboard.poll(0))
        for i,key in enumerate((65,66,67)):
            state.clear()
            state[key] = 0x8000
            active = keyboard.poll(.2+i*.2)
        self.assertTrue(active)
        state.clear()
        self.assertFalse(keyboard.poll(4))
        self.assertTrue(all(isinstance(t,float) for t in keyboard.downs))

    def test_direction_and_quiet_timer(self):
        self.assertEqual([direction_index(*p) for p in ((0,-1),(1,0),(0,1),(-1,0))],[0,4,8,12])
        self.assertTrue(ambient_due(601,0,0,enabled=True,idle=True,visible=True))
        self.assertFalse(ambient_due(601,0,0,enabled=False,idle=True,visible=True))

    def test_invalid_extensions_and_hotzones(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = {"schema_version":1,"id":"bad","name":"Bad","canvas":[32,32],"theme":{"accent":"#123456"},"actions":{"idle":{"frames":["../frame.png"],"fps":2}},"hotzones":[{"rect":[500,20,100,50],"action":"missing"}],"interactions":{"keyboard":"yes"}}
            (root / "character.json").write_text(json.dumps(doc),encoding="utf-8")
            result = validate(root,check_files=False)
            self.assertFalse(result["ok"])
            self.assertGreaterEqual(len(result["errors"]),4)


if __name__=="__main__":
    unittest.main()
