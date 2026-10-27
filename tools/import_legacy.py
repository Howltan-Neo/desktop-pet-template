"""Convert the local Xiaoan atlas and Xiaomou loose frames into reusable packs."""
from pathlib import Path
import argparse
import importlib.util
import json
import shutil
from PIL import Image


def dump(root, doc):
    (root / "character.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def migrate(source, dest, refresh=False):
    dest.mkdir(parents=True, exist_ok=True)
    normal = source / "桌宠小哞诞生记"
    spec = importlib.util.spec_from_file_location("legacy_lines", normal / "work/interactive/dialogue.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = json.loads((normal / "outputs/animations/manifest.json").read_text(encoding="utf-8"))
    for mode, ident, name in (("normal", "xiaomou", "小哞"), ("dog", "xiaomou-dog", "小狗哞")):
        root = dest / ident
        if root.exists() and not refresh:
            raise FileExistsError(f"Refusing to overwrite {root}")
        root.mkdir(exist_ok=True)
        actions = {}
        for full, info in manifest["states"].items():
            variant, key = full.split("/")
            if variant != mode:
                continue
            shutil.copytree(normal / "outputs/animations" / mode / key, root / "frames" / key, dirs_exist_ok=refresh)
            actions[key] = {"label": info.get("title", key), "frames": [f"frames/{key}/{i:02}.png" for i in range(info["frames"])],
                            "fps": 2 if key == "idle" else 1 if key == "work" else 2.38 if key.startswith("run_") else 1.33,
                            "dialogue": list(module.LINES[mode].get(key, []))}
        gaze = normal / "outputs/animations" / mode / "look_direction"
        if gaze.exists() and "look_direction" not in actions:
            shutil.copytree(gaze, root / "frames/look_direction", dirs_exist_ok=refresh)
            actions["look_direction"] = {"label": "环视", "frames": [f"frames/look_direction/{i:02}.png" for i in range(16)], "fps": 2, "dialogue": list(module.LINES[mode]["look"])}
        hotzones = [dict(rect=[41,26,192,215], action="pet_left"),dict(rect=[193,26,324,215],action="pet_front"),dict(rect=[325,26,471,215],action="pet_right")]
        if mode == "dog":
            hotzones = [dict(rect=[351,357,497,490],action="tail_tug"),dict(rect=[19,111,124,249],action="ear_left_01"),dict(rect=[388,111,493,249],action="ear_right_01")] + hotzones
        dump(root, {"schema_version":1,"id":ident,"name":name,"canvas":[512,512],
                    "theme":{"accent":"#AB7736","ink":"#624528","muted":"#8D6D44","surface":"#E8CC97","font":None},
                    "actions":actions,"hotzones":hotzones,
                    "interactions":{"click":"wave","double_click":"fitness","hold":"pet_rub","keyboard":True,"mouse_gaze":True,"ambient":["fitness","waiting","sleep","yawn","stretch","nuzzle"]}})
    root = dest / "xiaoan"
    if root.exists() and not refresh:
        raise FileExistsError(f"Refusing to overwrite {root}")
    root.mkdir(exist_ok=True)
    rows = {"idle":(0,6),"run_right":(1,8),"run_left":(2,8),"wave":(3,4),"sad":(5,8),"waiting":(6,6),"work":(7,6),"thinking":(8,6),"look_direction":(9,16)}
    extra = {"pet_front":(0,4),"hair_tug":(1,4),"wiggle":(2,4)}
    actions = {}
    labels = {"idle":"待机","run_right":"向右跑","run_left":"向左跑","wave":"招手","sad":"失落","waiting":"等待","work":"工作中","thinking":"沉思","look_direction":"环视","pet_front":"摸头","hair_tug":"拽发尾","wiggle":"扭屁股"}
    lines = {"wave":["嗨，见到你啦。","过来陪你一会儿。","今天也想陪着你。"],"pet_front":["唔……再摸一下嘛。","被你摸头，心情都软了。","这样陪着你，我很开心。"],"hair_tug":["哼，头发会乱的啦。","再拽就要你帮我梳好哦。"],"wiggle":["抓得到我吗？","嘿嘿，今天轮到我逗你啦。"],"work":["一起认真工作吧。","你忙你的，我在旁边陪你。"],"thinking":["让我想一想……"],"sad":["有点沮丧，抱抱。"],"waiting":["我在等你呀。"],"look_direction":["我在看你呢。"]}
    for filename, table in (("小安_宠物图集.png",rows),("小安_扩展动作图集.png",extra)):
        with Image.open(source / "桌宠小安诞生记/outputs" / filename) as atlas:
            atlas = atlas.convert("RGBA")
            for key,(row,count) in table.items():
                folder = root / "frames" / key
                folder.mkdir(parents=True,exist_ok=True)
                for i in range(count):
                    x, y = (i % 8)*192, (row + i//8)*208
                    if filename.startswith("小安_扩展"):
                        x, y = i*192, row*208
                    frame = atlas.crop((x,y,x+192,y+208))
                    # Preserve original cell's aspect ratio inside the common square canvas.
                    ratio = min(472/frame.width,512/frame.height)
                    frame = frame.resize((round(frame.width*ratio),round(frame.height*ratio)),Image.Resampling.LANCZOS)
                    square = Image.new("RGBA",(512,512))
                    square.alpha_composite(frame,((512-frame.width)//2,512-frame.height))
                    square.save(folder / f"{i:02}.png")
                actions[key] = {"label":labels[key],"frames":[f"frames/{key}/{i:02}.png" for i in range(count)],"fps":2 if key=="idle" else 2.38 if key.startswith("run_") else 1.33,"dialogue":lines.get(key,["我在这里陪着你。"])}
    dump(root,{"schema_version":1,"id":"xiaoan","name":"小安","canvas":[512,512],
               "theme":{"accent":"#639AB0","ink":"#3A535E","muted":"#66808C","surface":"#CFDFE8","font":None},"actions":actions,
               "aliases":{"pet_left":"pet_front","pet_right":"pet_front","pet_rub":"pet_front","fitness":"wiggle"},
               "hotzones":[{"rect":[90,20,420,260],"action":"pet_front"},{"rect":[60,261,170,375],"action":"hair_tug"}],
               "interactions":{"click":"wave","double_click":"wiggle","hold":"pet_front","keyboard":True,"mouse_gaze":True,"ambient":["waiting","thinking","wiggle"]}})
    print('Imported xiaoan, xiaomou and xiaomou-dog.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('dest',type=Path)
    parser.add_argument('--refresh',action='store_true',help='Overwrite the three previously migrated sample packs')
    args = parser.parse_args()
    migrate(args.source.resolve(),args.dest.resolve(),args.refresh)
