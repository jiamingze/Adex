"""Boundary-only transformations for untrusted model text."""


def strip_json_fence(value: str) -> str:
    """Remove optional outer JSON fences without scanning whitespace by backtracking.

    Internal Markdown/code belongs to JSON string values and must remain untouched.
    JSON decoding and schema validation still determine whether the result is valid.
    """
    raw = value.strip()
    if raw.startswith("```"):
        raw = raw[3:]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.lstrip()
    if raw.endswith("```"):
        raw = raw[:-3].rstrip()
    return raw
