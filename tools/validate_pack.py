"""CLI for the shared runtime character-pack validator."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "app"))
from pack_validation import validate, main
if __name__ == "__main__":
    sys.exit(main())
