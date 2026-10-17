import re
from fastapi import HTTPException


def validate_diagram(source):
    if len(source) > 20000 or not re.match(r"^\s*(flowchart|graph|sequenceDiagram|classDiagram)\b", source):
        raise HTTPException(422, "DIAGRAM_TYPE_OR_SIZE_INVALID")
    # Recognize complete arrow tokens, never strip apparent HTML then trust the remainder.
    if any(token.group() in ("<", ">") for token in re.finditer(r"-->>|->>|-->|<--|<->|->|[<>]", source)):
        raise HTTPException(422, "UNSAFE_DIAGRAM_SOURCE")
    if re.search(r"%%\{|\bclick\b|https?:|javascript:|\bstyle\b|\bclassDef\b", source, re.I):
        raise HTTPException(422, "UNSAFE_DIAGRAM_SOURCE")
    if len(source.splitlines()) > 150:
        raise HTTPException(422, "DIAGRAM_TOO_COMPLEX")
    return {"valid": True, "policy_version": "strict-v1"}
