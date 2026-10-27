"""Contract tests use a fake API client and never access a network or API key."""
import base64
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "tools"))
from ai_workflow import plan, generate, review


class FakeResponses:
    def __init__(self):
        self.calls = []
    def create(self, **request):
        self.calls.append(request)
        if "tools" in request:
            image = Image.new("RGBA",(1024,1024))
            image.paste((10,20,30,255),(200,200,800,900))
            buffer = io.BytesIO()
            image.save(buffer,format="PNG")
            return SimpleNamespace(id="fake-image",output=[SimpleNamespace(type="image_generation_call",result=base64.b64encode(buffer.getvalue()).decode())])
        prompt = request["input"][0]["content"][0]["text"]
        if prompt.startswith("Compare reference"):
            return SimpleNamespace(id="fake-review",output_text=json.dumps({"status":"revise","issues":[{"frame_index":0,"category":"anatomy","description":"test fixture","fix":"test only"}],"summary":"Fake fixture review"}))
        raise AssertionError("Tests should persist a known design, not ask a fake to design")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.reference = self.root / "source.png"
        Image.new("RGBA",(64,64),(10,30,40,255)).save(self.reference)
        self.pack = self.root / "pack"
        self.client = SimpleNamespace(responses=FakeResponses())
        plan(self.reference,self.pack,"example","示例","Keep exact face and costume", "#AB7736")
        self.doc = json.loads((self.pack / "character.json").read_text(encoding="utf-8"))
        self.doc["actions"] = {"idle":self.doc["actions"]["idle"]}
        self.doc["interactions"] = {"click":"idle","double_click":"idle","hold":"idle","keyboard":False,"mouse_gaze":False,"ambient":[]}
        (self.pack / "character.json").write_text(json.dumps(self.doc),encoding="utf-8")
        (self.pack / "ai-design.json").write_text(json.dumps({"idle":{"phases":["pose"]*6,"dialogue":["a","b","c","d"]}}),encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_budget_resumes_and_preserves_existing_frame(self):
        result = generate(self.pack,"fake-text","fake-image",1,client=self.client)
        self.assertEqual(result["generated_images"],1)
        first = self.pack / "frames/idle/00.png"
        before = first.read_bytes()
        generate(self.pack,"fake-text","fake-image",1,client=self.client)
        self.assertEqual(first.read_bytes(),before)
        self.assertTrue((self.pack / "frames/idle/01.png").exists())
        self.assertEqual(len(self.client.responses.calls),2)

    def test_review_missing_is_not_pass(self):
        result = review(self.pack,"fake-text",client=self.client)
        self.assertEqual(result["idle"]["status"],"incomplete")
        self.assertEqual(len(self.client.responses.calls),0)

    def test_repair_is_targeted_and_backed_up(self):
        generate(self.pack,"fake-text","fake-image",6,client=self.client)
        result = review(self.pack,"fake-text",client=self.client)
        self.assertEqual(result["idle"]["status"],"revise")
        self.assertTrue(result["idle"]["human_review_required"])
        self.assertEqual(len(result["idle"]["frame_sha256"]),6)
        generate(self.pack,"fake-text","fake-image",1,action="idle",repair=True,frame=0,client=self.client)
        self.assertEqual(len(list((self.pack / "previous-frames/idle").glob("*.png"))),1)

    def test_reference_changes_stop_generation(self):
        (self.pack / "reference.png").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError,"Reference changed"):
            generate(self.pack,"fake-text","fake-image",1,client=self.client)
        self.assertEqual(len(self.client.responses.calls),0)


if __name__=="__main__":
    unittest.main()
