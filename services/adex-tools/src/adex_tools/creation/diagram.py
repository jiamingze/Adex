import re
from fastapi import HTTPException


def validate_diagram(source):
    if len(source) > 20000 or not re.match(r"^\s*(flowchart|graph|sequenceDiagram|classDiagram)\b", source):
        raise HTTPException(422, "DIAGRAM_TYPE_OR_SIZE_INVALID")
    without_arrows = re.sub(r"-->|->>|-->>|->|-->|<--|<->", "", source)
    if re.search(r"%%\{|<|>|\bclick\b|https?:|javascript:|\bstyle\b|\bclassDef\b", without_arrows, re.I):
        raise HTTPException(422, "UNSAFE_DIAGRAM_SOURCE")
    if len(source.splitlines()) > 150:
        raise HTTPException(422, "DIAGRAM_TOO_COMPLEX")
    return {"valid": True, "policy_version": "strict-v1"}
