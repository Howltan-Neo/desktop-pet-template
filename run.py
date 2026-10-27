"""Launch a configured character pack on Windows."""
from pathlib import Path
import argparse
import json
import os
import sys


def main():
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    sys.path.insert(0, str(base / "app"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=base / "characters" / "xiaomou")
    parser.add_argument("--check", action="store_true", help="Validate resources without opening windows")
    parser.add_argument("--report",type=Path,help="Save the resource validation report as JSON")
    args = parser.parse_args()
    from pack_validation import validate
    report = validate(args.pack)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    if args.check or not report["ok"]:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    if os.name != "nt":
        parser.error("The desktop runtime currently requires Windows. Pack tools are cross-platform.")
    os.environ["DESKTOP_PET_PACK"] = str(args.pack.resolve())
    from desktop_pet import main as launch
    # The controller's legacy self-test parser should see only its own arguments.
    sys.argv = sys.argv[:1]
    launch()
    return 0


if __name__ == "__main__":
    sys.exit(main())
