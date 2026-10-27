"""Plan, generate, visually review, and repair a character with configurable AI models.

No network calls occur unless `generate` or `review` is explicitly invoked.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import io
import json
import math
import mimetypes
import os
import re
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from pack_validation import validate

STATES = {
    "idle": ("待机", "gentle breathing and blinking; feet and body anchor fixed", 6),
    "wave": ("招手", "raise one hand, wave with clear fingers, then lower naturally", 6),
    "pet_front": ("摸头", "softly bow head, close eyes, then recover; keep both arms complete", 6),
    "pet_left": ("左侧摸头", "tilt head to character right, gently react to touch from left", 6),
    "pet_right": ("右侧摸头", "tilt head to character left, gently react to touch from right", 6),
    "pet_rub": ("轻揉头顶", "bow and relax with subtle hair compression, no floating hair fragments", 6),
    "run_left": ("向左跑", "leftward run in place, alternate opposite arm and leg; contact, down, pass, up", 8),
    "run_right": ("向右跑", "rightward run in place, alternate opposite arm and leg; contact, down, pass, up", 8),
    "waiting": ("等待", "patient small weight shifts, calm anticipation", 6),
    "sad": ("失落", "gentle disappointed expression, subtle shoulders, recover without exaggerated distress", 6),
    "work": ("工作", "concentrated expression, plausible small working motions; complete anatomy", 6),
    "thinking": ("沉思", "small head tilt, eye movement and thoughtful hand gesture", 6),
    "sleep": ("睡觉", "comfortable resting pose with breathing and closed eyes", 6),
    "stretch": ("伸懒腰", "natural shoulder and elbow extension, ease into and out of stretch", 6),
    "yawn": ("打哈欠", "open mouth gently and cover with hand, then return", 6),
    "nuzzle": ("蹭蹭", "small affectionate lean and recover, keep center of mass plausible", 6),
    "look_direction": ("环视", "head and face orientation, real head silhouette changes; 0 up, clockwise every 22.5 degrees", 16),
}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def image_input(path):
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    return {"type":"input_image", "image_url":f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")}


def plan(reference, output, ident, name, constraints, accent):
    if output.exists():
        raise FileExistsError("Choose a new output directory; existing packs are never overwritten by plan")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", ident):
        raise ValueError("id must contain lowercase letters, numbers and hyphens")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
        raise ValueError("accent must be #RRGGBB")
    with Image.open(reference) as source:
        source.verify()
    output.mkdir(parents=True)
    ref = output / "reference.png"
    with Image.open(reference) as source:
        source.convert("RGBA").save(ref)
    actions = {}
    for key,(label,description,count) in STATES.items():
        actions[key] = {"label":label,"description":description,"frames":[f"frames/{key}/{i:02}.png" for i in range(count)],"fps":2.4 if key.startswith("run_") else 2 if key=="idle" else 1.33,"dialogue":[]}
    doc = {"schema_version":1,"id":ident,"name":name,"canvas":[512,512],"theme":{"accent":accent,"font":None},"actions":actions,
           "hotzones":[],"interactions":{"click":"wave","double_click":"stretch","hold":"pet_rub","keyboard":True,"mouse_gaze":True,"ambient":["waiting","sleep","stretch","yawn","nuzzle"]}}
    write_json(output / "character.json",doc)
    brief = {"reference":"reference.png","reference_sha256":hashlib.sha256(ref.read_bytes()).hexdigest(),"constraints":constraints,
             "goal":"Preserve the exact character identity; design distinct complete animation poses, expressions, motion phases and fitting dialogue.",
             "acceptance":["preserve face, hair, costume and accessories", "no missing or extra limbs; stable clothes and correct occlusions", "full silhouette with padding, no clipped edges or ghosting", "consistent scale, canvas center and ground baseline", "natural anticipation, weight transfer, follow-through, loop continuity", "16 gaze views must change head and face, not only translate pupils", "contact sheets plus per-action GIF must be visually reviewed", "manual Windows interaction acceptance is required"]}
    write_json(output / "ai-brief.json",brief)
    (output / "AI_TASK.md").write_text("# AI 角色制作任务\n\n读取 ai-brief.json、character.json 和 reference.png。先检查身份特征并生成基准待机帧。逐动作设计动作相位、细节、表情与独立帧；不得用整图平移或缩放冒充动作。每个动作生成至少四条符合人物性格的简短中文台词。按 frames 路径输出 RGBA PNG；补充基于新角色位置的 hotzones。运行 tools/qa_pack.py，查看全部逐帧总览及 GIF，记录问题及修订；不能以自动检查通过代替视觉审查。记录 ai-review.json；运行时测试完成前不能标为最终通过。\n",encoding="utf-8")
    return {"pack":str(output),"planned_frames":sum(len(a["frames"]) for a in actions.values()),"network_used":False}


def client_from_env():
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY locally; never put keys in character.json or commit them")
    from openai import OpenAI
    return OpenAI(max_retries=0, timeout=240)


def parse_json_response(response):
    text = response.output_text.strip()
    if text.startswith("```"):
        text = text.split("\n",1)[1].rsplit("```",1)[0]
    return json.loads(text)


def generate(root, text_model, image_model, max_images, action=None, repair=False, client=None, frame=None):
    if max_images < 1 or max_images > 200:
        raise ValueError("max-images must be in 1..200")
    config_report = validate(root, check_files=False)
    if not config_report["ok"]:
        raise ValueError("Invalid manifest: " + "; ".join(config_report["errors"]))
    if repair and (action is None or frame is None):
        raise ValueError("Repair requires --action and --frame to target one inspected frame")
    client = client or client_from_env()
    doc = json.loads((root / "character.json").read_text(encoding="utf-8"))
    brief = json.loads((root / "ai-brief.json").read_text(encoding="utf-8"))
    from character_pack import CharacterPack
    pack = CharacterPack(root)
    reference = pack.path(brief["reference"])
    if hashlib.sha256(reference.read_bytes()).hexdigest() != brief["reference_sha256"]:
        raise ValueError("Reference changed; update and review the brief before generating")
    keys = [action] if action else list(doc["actions"])
    if any(key not in doc["actions"] for key in keys):
        raise ValueError("Unknown action")
    # Design is persisted before images, so interrupted runs can resume.
    design_path = root / "ai-design.json"
    design = json.loads(design_path.read_text(encoding="utf-8")) if design_path.exists() else {}
    missing_design = [key for key in keys if key not in design]
    if missing_design:
        request = "Design animation and dialogue for this exact character. Return only JSON object keyed by requested action. Each value: {identity_notes:string, phases:[one detailed visual instruction for each frame], dialogue:[4 short distinct Chinese lines], hotzones:[{rect:[x1,y1,x2,y2],action:string}]}. Rectangles use 512x512 canvas coordinates; include anatomically appropriate touch regions only. For look_direction phases are orientation views starting up then clockwise. Never assert quality passed. " + json.dumps({"brief":brief,"actions":{k:doc["actions"][k] for k in missing_design}},ensure_ascii=False)
        response = client.responses.create(model=text_model,input=[{"role":"user","content":[{"type":"input_text","text":request},image_input(reference)]}])
        generated = parse_json_response(response)
        for key in missing_design:
            value = generated.get(key,{})
            if len(value.get("phases",[])) != len(doc["actions"][key]["frames"]) or any(not isinstance(p,str) or not p.strip() for p in value.get("phases",[])):
                raise ValueError(f"AI design for {key} has invalid phases; no images requested")
            lines = value.get("dialogue")
            if not isinstance(lines,list) or len(lines)<4 or any(not isinstance(s,str) or not s.strip() for s in lines):
                raise ValueError(f"AI dialogue for {key} is invalid")
            design[key] = value
            doc["actions"][key]["dialogue"] = lines
        write_json(design_path,design)
        regions = []
        for value in design.values():
            for region in value.get("hotzones",[]):
                if isinstance(region,dict) and region not in regions:
                    regions.append(region)
        doc["hotzones"] = regions
        write_json(root / "character.json",doc)
        config_report = validate(root,check_files=False)
        if not config_report["ok"]:
            raise ValueError("AI returned invalid character settings; fix before image generation: " + "; ".join(config_report["errors"]))
    review = json.loads((root / "ai-review.json").read_text(encoding="utf-8")) if repair and (root / "ai-review.json").exists() else {}
    completed = 0
    for key in keys:
        value = doc["actions"][key]
        for index, filename in enumerate(value["frames"]):
            if frame is not None and index != frame:
                continue
            target = pack.path(filename)
            if target.exists() and not repair:
                continue
            if completed >= max_images:
                return {"generated_images":completed,"paused_at":filename,"complete":False}
            prompt = ("Draw ONE complete transparent-background animation frame of exactly the reference character. Full body, no text, no frame grid, no extra people. Preserve costume, colors, accessories, facial identity and art style. Character should occupy about 85% of height with stable feet baseline around 94% height. Use the first reference for identity and the second (if provided) for scale and ground alignment. No clipped silhouette, duplicated limbs, ghosts or erased facial features. Real pose changes, not whole-image shifts. "
                      + json.dumps({"constraints":brief["constraints"],"action":key,"frame_index":index,"frame_count":len(value["frames"]),"phase":design[key]["phases"][index],"review_fixes":review.get(key,{})},ensure_ascii=False))
            content = [{"type":"input_text","text":prompt},image_input(reference)]
            baseline = pack.path(doc["actions"]["idle"]["frames"][0])
            if baseline.exists() and baseline != target:
                content.append(image_input(baseline))
            response = client.responses.create(model=text_model,input=[{"role":"user","content":content}],tools=[{"type":"image_generation","model":image_model,"action":"edit","background":"transparent","output_format":"png","size":"1024x1024","quality":"high"}])
            images = [part.result for part in response.output if part.type=="image_generation_call" and getattr(part,"result",None)]
            if len(images)!=1:
                raise RuntimeError("Expected one generated image; existing assets preserved")
            data = base64.b64decode(images[0], validate=True)
            raw = root / "generated-originals" / key / f"{index:02}.png"
            raw.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():
                backup = root / "previous-frames" / key / f"{index:02}-{hashlib.sha256(target.read_bytes()).hexdigest()[:12]}.png"
                backup.parent.mkdir(parents=True,exist_ok=True)
                if not backup.exists():
                    backup.write_bytes(target.read_bytes())
            if raw.exists():
                raw_backup = raw.with_name(raw.stem + "-" + hashlib.sha256(raw.read_bytes()).hexdigest()[:12] + ".png")
                if not raw_backup.exists():
                    raw_backup.write_bytes(raw.read_bytes())
            with Image.open(io.BytesIO(data)) as source:
                art = source.convert("RGBA")
                if art.getchannel("A").getextrema()[0] == 255:
                    raise ValueError(f"{key}/{index}: generated image has no transparent background; original saved nowhere")
                art = art.resize(tuple(doc["canvas"]),Image.Resampling.LANCZOS)
                target.parent.mkdir(parents=True,exist_ok=True)
                temporary = target.with_suffix(".tmp.png")
                art.save(temporary)
            raw.write_bytes(data)
            temporary.replace(target)
            completed += 1
            write_json(root / "generation-progress.json",{"last_frame":filename,"images_this_run":completed,"model":text_model,"image_model":image_model,"response_id":response.id,"visual_review":"pending"})
            print(f"saved {filename}",flush=True)
    report = validate(root)
    return {"generated_images":completed,"complete":report["ok"],"visual_review":"pending","machine_checks":report}


def review(root, text_model, action=None, client=None):
    client = client or client_from_env()
    from character_pack import CharacterPack
    pack = CharacterPack(root)
    reference = root / "reference.png"
    results = json.loads((root / "ai-review.json").read_text(encoding="utf-8")) if (root / "ai-review.json").exists() else {}
    if action is not None and action not in pack.actions:
        raise ValueError("Unknown action")
    for key in ([action] if action else list(pack.actions)):
        files = pack.action(key)["frames"]
        if any(not pack.path(f).exists() for f in files):
            results[key] = {"status":"incomplete","issues":["Missing frames"]}
            continue
        content = [{"type":"input_text","text":"Compare reference (first image) to ordered animation frames. Return JSON {status:'pass'|'revise',issues:[{frame_index:int,category:string,description:string,fix:string}],summary:string}. Inspect identity, expressions, hair/face cleanup, limb count and occlusion, clipping, anatomy, clothing, center/ground alignment, anticipation/contact/recovery, first-last continuity. For directional gaze ensure head/face rotates rather than only pupils. Never certify biomechanics from stills. Action: " + key},image_input(reference)]
        content.extend(image_input(pack.path(f)) for f in files)
        response = client.responses.create(model=text_model,input=[{"role":"user","content":content}])
        value = parse_json_response(response)
        if value.get("status") not in ("pass","revise") or not isinstance(value.get("issues"),list):
            raise ValueError("Malformed visual review; no pass recorded")
        value["response_id"] = response.id
        value["frame_sha256"] = {f:hashlib.sha256(pack.path(f).read_bytes()).hexdigest() for f in files}
        value["human_review_required"] = True
        results[key] = value
        write_json(root / "ai-review.json",results)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command",required=True)
    p = commands.add_parser("plan")
    p.add_argument("reference",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--id",required=True)
    p.add_argument("--name",required=True)
    p.add_argument("--constraints",required=True)
    p.add_argument("--accent",default="#AB7736")
    for command in ("generate","review"):
        p = commands.add_parser(command)
        p.add_argument("pack",type=Path)
        p.add_argument("--text-model",required=True)
        p.add_argument("--action")
        if command=="generate":
            p.add_argument("--image-model",required=True)
            p.add_argument("--max-images",type=int,default=1)
            p.add_argument("--repair",action="store_true")
            p.add_argument("--frame",type=int)
    args = parser.parse_args()
    if args.command=="plan":
        result = plan(args.reference.resolve(),args.output.resolve(),args.id,args.name,args.constraints,args.accent)
    elif args.command=="generate":
        result = generate(args.pack.resolve(),args.text_model,args.image_model,args.max_images,args.action,args.repair,frame=args.frame)
    else:
        result = review(args.pack.resolve(),args.text_model,args.action)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
