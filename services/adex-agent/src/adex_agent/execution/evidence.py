"""Stable observation identity, derived from tool readback rather than model prose."""

import re
from adex_kernel.core import digest


def observation_fingerprint(items):
    facts = set()
    for item in items:
        url = item.get("url", "")
        content = item.get("extracted_text") or item.get("content") or item.get("snippet") or ""
        if (
            not isinstance(url, str)
            or not url.startswith("https://")
            or not isinstance(content, str)
            or not content.strip()
        ):
            continue
        # Fetch times, item ordering and whitespace vary without a source fact changing.
        # Do not remove dates/numbers from source text: they may be the actual new fact.
        facts.add(
            (
                url,
                re.sub(r"\s+", " ", str(item.get("title", ""))).strip(),
                re.sub(r"\s+", " ", content).strip(),
            )
        )
    return digest(sorted(facts)) if facts else None


def cards_fingerprint(cards):
    return observation_fingerprint(
        [
            item
            for card in cards
            if card.get("type") == "source_list"
            for item in card.get("data", {}).get("items", [])
            if isinstance(item, dict)
        ]
    )
