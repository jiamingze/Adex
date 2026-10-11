from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key, value)
    return dict(os.environ)
