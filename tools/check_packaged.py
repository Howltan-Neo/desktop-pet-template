"""Bounded lifecycle check of an independently built Windows executable."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import time
from PIL import ImageGrab


def check(executable, output, name, pack=None):
    output.mkdir(parents=True,exist_ok=True)
    env = dict(os.environ,LOCALAPPDATA=str(output / "user-data"))
    command = [str(executable)] + (["--pack",str(pack)] if pack else [])
    process = subprocess.Popen(command,env=env,cwd=executable.parent)
    user32 = ctypes.windll.user32
    found = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    def visit(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd,title,len(title))
        if pid.value==process.pid and title.value==name and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True
    report = {"window_found":False,"normal_exit":False,"physical_interaction_test":"not performed"}
    try:
        deadline = time.monotonic()+12
        while time.monotonic()<deadline and process.poll() is None and not found:
            user32.EnumWindows(callback_type(visit),0)
            time.sleep(.15)
        if found:
            time.sleep(.8)
            ImageGrab.grab(window=int(found[0])).save(output / "packaged-window.png")
            report["window_found"] = True
            user32.PostMessageW.argtypes = [wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
            user32.PostMessageW(found[0],0x10,0,0)
            try:
                process.wait(timeout=8)
                report["normal_exit"] = process.returncode==0
            except subprocess.TimeoutExpired:
                pass
        report["exit_code"] = process.poll()
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        report["ok"] = report["window_found"] and report["normal_exit"]
        (output / "report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report


if __name__=="__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("executable",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--name",default="小哞")
    p.add_argument("--pack",type=Path)
    a=p.parse_args()
    result=check(a.executable.resolve(),a.output.resolve(),a.name,a.pack.resolve() if a.pack else None)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result["ok"] else 1)
