import re
from fastapi import HTTPException


def validate_diagram(source):
    if len(source) > 20000 or not re.match(r"^\s*(flowchart|graph|sequenceDiagram|classDiagram)\b", source):
        raise HTTPException(422, "DIAGRAM_TYPE_OR_SIZE_INVALID")
    # Recognize literal arrow tokens; never filter/rewrite HTML and trust the remainder.
    cursor = 0
    arrows = ("-->>", "->>", "-->", "<--", "<->", "->")
    while cursor < len(source):
        arrow = next((token for token in arrows if source.startswith(token, cursor)), None)
        if arrow:
            cursor += len(arrow)
        elif source[cursor] in "<>":
            raise HTTPException(422, "UNSAFE_DIAGRAM_SOURCE")
        else:
            cursor += 1
    if re.search(r"%%\{|\bclick\b|https?:|javascript:|\bstyle\b|\bclassDef\b", source, re.I):
        raise HTTPException(422, "UNSAFE_DIAGRAM_SOURCE")
    if len(source.splitlines()) > 150:
        raise HTTPException(422, "DIAGRAM_TOO_COMPLEX")
    return {"valid": True, "policy_version": "strict-v1"}
