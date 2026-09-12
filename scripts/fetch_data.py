"""Download the CHCD v3.0.1 CSV release into data/raw/.

The full upstream repository is ~360 MB because it carries V1, V2 and V3
side by side. Only the two V3 files are needed here, so they are fetched
directly instead of cloned. Files already present are left alone unless
--force is given.

Source: https://github.com/chcdatabase/data (CC BY 4.0)
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

RAW_BASE = "https://raw.githubusercontent.com/chcdatabase/data/main/CSV_V3"
FILES = ("chcd_v3.0.1_nodes.csv", "chcd_v3.0.1_rels.csv")

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(name: str, *, force: bool) -> Path:
    target = RAW_DIR / name
    if target.exists() and not force:
        print(f"  {name}: already present ({target.stat().st_size:,} bytes)")
        return target

    url = f"{RAW_BASE}/{name}"
    print(f"  {name}: downloading from {url}")
    tmp = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(url) as response, tmp.open("wb") as handle:
        while chunk := response.read(1 << 20):
            handle.write(chunk)
    tmp.replace(target)
    print(f"  {name}: {target.stat().st_size:,} bytes")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="re-download even if the file exists"
    )
    parser.add_argument(
        "--checksums", action="store_true", help="print sha256 of each file"
    )
    args = parser.parse_args(argv)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"CHCD v3.0.1 -> {RAW_DIR}")
    paths = [fetch(name, force=args.force) for name in FILES]

    if args.checksums:
        for path in paths:
            print(f"  {path.name}: sha256={sha256(path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
