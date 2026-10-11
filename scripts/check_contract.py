import json
from pathlib import Path
from openapi_spec_validator import validate

root = Path(__file__).resolve().parents[1]
spec = json.loads((root / "packages/contracts/core.openapi.json").read_text())
validate(spec)
ids = [op["operationId"] for path in spec["paths"].values() for op in path.values()]
assert len(set(ids)) == len(ids)
print(f"OpenAPI validated: {len(ids)} operations")
