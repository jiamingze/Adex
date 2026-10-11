"""Fail fast when composition/transport boundaries collapse back into flat packages."""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors = []
for service, package in [("adex-agent", "adex_agent"), ("adex-tools", "adex_tools")]:
    base = ROOT / "services" / service / "src" / package
    allowed_root = {"__init__.py", "main.py", "dependencies.py"}
    for path in base.rglob("*.py"):
        relative = path.relative_to(base)
        if len(relative.parts) == 1 and path.name not in allowed_root:
            errors.append(
                f"{relative}: capability implementation must have an owning module"
            )
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if relative.parts[0] != "api" and path.name != "main.py" and module.startswith(package + ".api"):
                    errors.append(
                        f"{relative}: implementation imports HTTP adapter {module}"
                    )
                if module == package + ".main":
                    errors.append(
                        f"{relative}: importing composition entrypoint creates lifecycle coupling"
                    )
            if path.name == "main.py" and isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                if node.name not in {"lifespan", "error", "create_app"}:
                    errors.append(
                        f"{relative}: business function {node.name} in entrypoint"
                    )
    if len((base / "main.py").read_text().splitlines()) > 90:
        errors.append(f"{service}: entrypoint exceeds composition-only size")

for service, namespace, entry in [
    ("adex-app", "app", "AppMain"),
    ("adex-automation", "automation", "AutomationMain"),
]:
    base = ROOT / "services" / service / "src/main/java/io/adex" / namespace
    sources = {p.stem: p for p in base.rglob("*.java")}
    controllers = {
        name for name, path in sources.items() if "@RestController" in path.read_text()
    }
    for name, path in sources.items():
        source = path.read_text()
        if path.parent == base and name != entry:
            errors.append(f"{service}/{name}: implementation in root package")
        # A controller is an entry adapter, never a dependency of another bean.
        for controller in controllers - {name}:
            if re.search(r"\b" + controller + r"\s+\w+", source):
                errors.append(f"{name}: depends on HTTP controller {controller}")
        if name.endswith(("Service", "Gateway")) and "jakarta.servlet" in source:
            errors.append(f"{name}: application use case depends on servlet transport")

if errors:
    raise SystemExit("\n".join(errors))
print(
    "Architecture checks passed: capability ownership, composition and HTTP dependency boundaries."
)
