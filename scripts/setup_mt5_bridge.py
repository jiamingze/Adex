"""Install isolated read-only Python bridge dependencies in the existing MT5 Wine prefix.

No pip scripts, login changes, Algo Trading toggles or order submission. Downloads
are from python.org / PyPI; wheel SHA-256 is verified against PyPI metadata.
"""

import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile


def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def main():
    prefix = Path.home() / "Library/Application Support/net.metaquotes.wine.metatrader5"
    if not (prefix / "drive_c/Program Files/MetaTrader 5/terminal64.exe").is_file():
        raise SystemExit("BLOCKED_EXTERNAL: installed MT5 prefix not found")
    root = prefix / "drive_c/adex-python"
    root.mkdir(mode=0o700, exist_ok=True)
    if not (root / "python.exe").exists():
        data = fetch("https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            archive.extractall(root)
    site = root / "Lib/site-packages"
    site.mkdir(parents=True, exist_ok=True)
    for package, version in [("numpy", "2.2.6"), ("MetaTrader5", "5.0.6231")]:
        metadata = json.loads(fetch(f"https://pypi.org/pypi/{package}/{version}/json"))
        wheel = next(x for x in metadata["urls"] if x["filename"].endswith("cp312-cp312-win_amd64.whl"))
        data = fetch(wheel["url"])
        if hashlib.sha256(data).hexdigest() != wheel["digests"]["sha256"]:
            raise SystemExit("PACKAGE_CHECKSUM_MISMATCH")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            archive.extractall(site)
        print(f"Installed {package}=={version} (SHA-256 verified)")
    (root / "python312._pth").write_text("python312.zip\n.\nLib/site-packages\n", encoding="utf-8")
    print("Read-only MT5 Python runtime ready; trading settings unchanged")


if __name__ == "__main__":
    main()
