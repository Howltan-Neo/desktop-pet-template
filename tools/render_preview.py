"""Render the actual glass panel artwork without creating any desktop windows."""
import argparse
import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "app"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack",type=Path)
    parser.add_argument("output",type=Path)
    args = parser.parse_args()
    os.environ["DESKTOP_PET_PACK"] = str(args.pack.resolve())
    from glass_ui import GlassArtwork, PACK, window_bitmap
    from speech_card import SpeechCard
    args.output.mkdir(parents=True,exist_ok=True)
    avatar = Image.open(PACK.frame_path("idle")).convert("RGBA")
    avatar = avatar.crop(avatar.getchannel("A").getbbox())
    actions = [("look" if key=="look_direction" else key,value.get("label",key)) for key,value in PACK.actions.items()]
    state = dict(scale=1,proactive=True,topmost=True,actions=actions,page=0,dog=False)
    for kind,size in (("menu",(420,670)),("actions",(420,720)),("tray",(340,480))):
        for background in ("light","dark"):
            backdrop = Image.new("RGB",size,(30,40,58) if background=="dark" else (221,231,242))
            art = GlassArtwork(kind,size,avatar,backdrop)
            image = art.render(**state)
            image.save(args.output / f"{kind}-{background}.png")
            assert window_bitmap(image,backdrop).getpixel((0,0))==(255,0,254)
    SpeechCard.render("你好，我会在这里陪着你。你也可以为我设计自己的动作和台词。",1,True).save(args.output / "speech.png")
    print(str(args.output.resolve()))


if __name__=="__main__":
    main()
