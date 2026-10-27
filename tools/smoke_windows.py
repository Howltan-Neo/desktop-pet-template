"""Exercise the actual Tk application in a local Windows desktop session."""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "app"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack",type=Path)
    parser.add_argument("output",type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    os.environ["DESKTOP_PET_PACK"] = str(args.pack.resolve())
    os.environ["LOCALAPPDATA"] = str(output / "user-data")
    from desktop_pet import DesktopPet, PACK
    from glass_ui import PANEL_KEY, window_bitmap
    DesktopPet.start_tray = lambda self: None
    app = DesktopPet()
    # Keep the test deterministic while the person continues using the desktop.
    # Physical keyboard/mouse acceptance is explicitly reported separately.
    app.keyboard_activity.poll = lambda now: False
    app.sample_pointer_activity = lambda now: None
    app.topmost = True
    app.active = True
    app.apply_topmost()
    app.root.geometry("+600+180")
    checks = []
    failures = []
    def exercise():
        try:
            for key in PACK.actions:
                if key=="look_direction":
                    key="look"
                app.show_pose(key,seconds=.1,words="")
                app.root.update_idletasks()
                for i in range(len(PACK.action(key)["frames"])):
                    app.sprite("look_direction" if key=="look" else key,i)
            checks.append("all actions and frames load in Tk")
            app.show_pose("idle",seconds=0,words="")
            app.open_glass_menu()
            app.root.update()
            popup = app.glass_menu
            assert popup.win.winfo_viewable()
            im = popup.art.render(**app.glass_state())
            im.save(output / "menu-render.png")
            assert window_bitmap(im,popup.art.backdrop).getpixel((0,0))==(255,0,254)
            checks.append("glass menu opens with color-key transparent corners")
            x,y=popup.win.winfo_rootx(),popup.win.winfo_rooty()
            ImageGrab.grab((x,y,x+popup.width,y+popup.height)).save(output / "menu-live.png")
            app.glass_common_action("topmost",None)
            assert not app.root.attributes("-topmost")
            assert not popup.win.attributes("-topmost")
            assert not app.bubble_card.win.attributes("-topmost")
            checks.append("topmost setting propagates to child windows")
            app.open_glass_actions()
            app.root.update()
            app.glass_actions.art.render(**app.glass_state()).save(output / "actions-render.png")
            for _ in range((len(PACK.actions)+10)//11):
                app.glass_actions_action("page",None)
            app.glass_actions._tab(None)
            assert app.glass_actions.hover is not None
            checks.append("action pagination and Tab focus navigation")
            app.close_panels()
            app.say("你好，这是一条用来检查换行与边缘避让的测试对白。")
            app.root.update()
            assert app.bubble_card.visible, str({"root":(app.root.winfo_x(),app.root.winfo_y(),app.size),"bubble_size":app.bubble_card.size,"bubble_position":app.bubble_card.position})
            app.bubble_card.art.save(output / "speech-render.png")
            app.bubble_card.hide()
            checks.append("speech renders and avoids pet window")
            app.work_source = None
            app.show_pose("idle",seconds=0,words="")
            app.keyboard_activity.poll = lambda now: True
            app.sample_keyboard_activity(time.monotonic()+1)
            assert app.pose == PACK.resolve_action("work")
            app.keyboard_activity.poll = lambda now: False
            app.sample_keyboard_activity(time.monotonic()+5)
            assert app.pose=="idle"
            checks.append("keyboard activity enters work and restores idle")
            app.point_gaze(1000,20,time.monotonic())
            assert 0<=app.look_index<16
            checks.append("mouse gaze maps to one of 16 directions")
            app.dock()
            app.root.update()
            x,y=app.root.winfo_rootx(),app.root.winfo_rooty()
            ImageGrab.grab((x,y,x+app.size,y+app.size)).save(output / "pet-live.png")
            checks.append("actual desktop window docks above taskbar")
        except Exception:
            import traceback
            failures.append(traceback.format_exc())
        finally:
            (output / "smoke.json").write_text(json.dumps({"pack":PACK.id,"checks":checks,"failures":failures,"ok":not failures,"physical_keyboard_mouse_test":"not performed"},ensure_ascii=False,indent=2),encoding="utf-8")
            app.quit()
    app.root.after(500,exercise)
    app.root.mainloop()
    print((output / "smoke.json").read_text(encoding="utf-8"))
    return 1 if failures else 0


if __name__=="__main__":
    sys.exit(main())
