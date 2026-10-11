import shutil
import subprocess

failed = []
for name in ["java", "mvn", "uv", "pnpm", "redis-server"]:
    if not shutil.which(name):
        failed.append(name)
java = (
    subprocess.run(["java", "-version"], capture_output=True, text=True)
    if shutil.which("java")
    else None
)
if java and 'version "21' not in java.stderr:
    failed.append("Java 21")
print(
    "Missing: " + ", ".join(failed)
    if failed
    else "Toolchain ready: Java 21, Maven, uv, pnpm, Redis"
)
print(
    "Docker/Elasticsearch is optional for native development; required to verify container deployment profile."
)
raise SystemExit(bool(failed))
