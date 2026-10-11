"""Bounded subprocess for untrusted PDF/text. No provider credentials in environment."""

import json
import sys
import resource
from pathlib import Path

resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
if sys.platform == "linux":
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
path = Path(sys.argv[1])
if path.stat().st_size > 25 * 1024 * 1024:
    raise SystemExit(2)
with path.open("rb") as stream:
    head = stream.read(8)
if head.startswith(b"%PDF"):
    from pypdf import PdfReader

    reader = PdfReader(path, strict=True)
    if len(reader.pages) > 100:
        raise SystemExit(2)
    pieces = []
    size = 0
    for page in reader.pages:
        value = (page.extract_text() or "")[:12000]
        size += len(value)
        pieces.append(value)
        if size >= 40000:
            break
    text = "\n".join(pieces)[:40000]
else:
    data = path.read_bytes()[:120000]
    if b"\x00" in data:
        raise SystemExit(2)
    text = data.decode("utf-8")[:40000]
print(json.dumps({"text": text}, ensure_ascii=False))
