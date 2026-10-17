"""Bounded website observations for multi-page product research, never transaction receipts."""

from datetime import datetime, timezone
from urllib.parse import urlsplit


class EvidenceNotebook:
    def __init__(self, saved=None):
        self.pages = []
        for page in (saved or [])[-10:]:
            if isinstance(page, dict) and page.get("url", "").startswith("https://"):
                self.pages.append(
                    {
                        k: str(page.get(k, ""))[:limit]
                        for k, limit in [
                            ("url", 2000),
                            ("title", 200),
                            ("observation_id", 100),
                            ("observed_at", 50),
                            ("visible_text", 1600),
                        ]
                    }
                )

    def observe(self, view):
        url = view.get("url", "")
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or view.get("access_block")
            or view.get("login_form")
        ):
            return
        text = "\n".join(
            str(n.get("name", ""))[:500]
            for n in view.get("nodes", [])
            if n.get("role") in ("StaticText", "heading", "link") and not n.get("protected")
        )[:1600]
        if not text.strip():
            return
        identity = view.get("observation_id", "")
        if any(
            p["url"] == url and p["observation_id"] == identity and p["visible_text"] == text
            for p in self.pages
        ):
            return
        page = {
            "url": url,
            "title": str(view.get("title", ""))[:200],
            "observation_id": identity,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "visible_text": text,
        }
        self.pages = [p for p in self.pages if p["url"] != url][-9:] + [page]

    def snapshot(self):
        return [dict(p) for p in self.pages]
