import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from validate_pack import validate


class PackValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(self.root / "frame.png")
        self.doc = {"schema_version": 1, "id": "example", "name": "测试",
                    "canvas": [32, 32], "theme": {"accent": "#123456", "font": None},
                    "actions": {"idle": {"frames": ["frame.png"], "fps": 3, "dialogue": []}}}

    def tearDown(self):
        self.tmp.cleanup()

    def run_pack(self):
        (self.root / "character.json").write_text(json.dumps(self.doc), encoding="utf-8")
        return validate(self.root)

    def test_valid_and_warning(self):
        result = self.run_pack()
        self.assertTrue(result["ok"])
        self.assertEqual(result["frames_checked"], 1)
        self.assertTrue(result["manual_review_required"])
        self.assertTrue(result["warnings"])

    def test_escape_and_invalid_image_are_errors(self):
        self.doc["actions"]["idle"]["frames"] = ["../outside.png", "missing.png"]
        result = self.run_pack()
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["errors"]), 2)

    def test_transparency_and_dimensions(self):
        Image.new("RGBA", (8, 8)).save(self.root / "frame.png")
        result = self.run_pack()
        self.assertFalse(result["ok"])
        self.assertTrue(any("fully transparent" in e for e in result["errors"]))
        self.assertTrue(any("dimensions" in e for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
