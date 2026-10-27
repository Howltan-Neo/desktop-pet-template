"""Render every action as a contact sheet and GIF, with reproducible file hashes."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "app"))
from character_pack import CharacterPack
from pack_validation import validate


def render(root, output):
    report = validate(root)
    if not report["ok"]:
        return report
    pack = CharacterPack(root)
    output.mkdir(parents=True,exist_ok=True)
    report["actions"] = {}
    for key, action in pack.actions.items():
        thumbs, gif_frames, fingerprints, hashes, bounds = [], [], [], {}, []
        for index, filename in enumerate(action["frames"]):
            path = pack.path(filename)
            with Image.open(path) as source:
                art = source.convert("RGBA")
            fingerprints.append(hashlib.sha256(art.tobytes()).hexdigest())
            hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
            bbox = art.getchannel("A").getbbox()
            bounds.append(bbox)
            tile = Image.new("RGB",(168,190),(239,242,245))
            for y in range(0,168,12):
                for x in range(0,168,12):
                    if (x//12+y//12)%2:
                        ImageDraw.Draw(tile).rectangle((x,y,x+11,y+11),fill=(214,222,229))
            small = art.resize((168,168),Image.Resampling.LANCZOS)
            tile.paste(small,(0,0),small)
            ImageDraw.Draw(tile).text((6,173),f"{key} {index:02}",fill=(30,40,50))
            thumbs.append(tile)
            gif_frames.append(tile.crop((0,0,168,168)))
        cols = min(8,len(thumbs))
        sheet = Image.new("RGB",(cols*168,((len(thumbs)+cols-1)//cols)*190),"white")
        for i,tile in enumerate(thumbs):
            sheet.paste(tile,((i%cols)*168,(i//cols)*190))
        sheet.save(output / f"{key}.png")
        gif_frames[0].save(output / f"{key}.gif",save_all=True,append_images=gif_frames[1:],duration=round(1000/action["fps"]),loop=0)
        clipped = [i for i,b in enumerate(bounds) if b and (b[0]==0 or b[1]==0 or b[2]==pack.data["canvas"][0] or b[3]==pack.data["canvas"][1])]
        report["actions"][key] = {"frames":len(thumbs),"distinct_frames":len(set(fingerprints)),"touches_canvas_edge":clipped,"bounds":bounds,"sha256":hashes}
        if len(set(fingerprints))<len(fingerprints):
            report["warnings"].append(f"{key}: repeated decoded frames; inspect motion")
        if clipped:
            report["warnings"].append(f"{key}: frames touch canvas edge; inspect clipping")
    report["visual_review"] = "pending"
    (output / "report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report


if __name__=="__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("pack",type=Path)
    p.add_argument("output",type=Path)
    a = p.parse_args()
    r = render(a.pack.resolve(),a.output.resolve())
    print(json.dumps({k:v for k,v in r.items() if k!="actions"},ensure_ascii=False,indent=2))
    sys.exit(0 if r["ok"] else 1)
