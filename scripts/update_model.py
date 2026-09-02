#!/usr/bin/env python3
"""Download a verified F1DB release and rerun the model only when data changed."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

API = "https://api.github.com/repos/f1db/f1db/releases/latest"
ASSET = "f1db-sqlite.zip"


def download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "f1metrix-updater/1"})
    with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as out:
        while chunk := response.read(1024 * 1024):
            out.write(chunk)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data", type=Path)
    parser.add_argument("--output", default="data/model-output.json", type=Path)
    parser.add_argument("--method", choices=("nuts", "advi"), default=os.getenv("F1METRIX_METHOD", "nuts"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)

    request = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json", "User-Agent": "f1metrix-updater/1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.load(response)
    assets = {asset["name"]: asset["browser_download_url"] for asset in release["assets"]}
    tag = release["tag_name"]
    state_path = args.data_dir / "f1db-release.json"
    if not args.force and state_path.exists() and json.loads(state_path.read_text()).get("tag") == tag:
        print(f"F1DB {tag} already modeled")
        return

    with tempfile.TemporaryDirectory(dir=args.data_dir) as temporary:
        temp = Path(temporary)
        archive, checksums = temp / ASSET, temp / "checksums.txt"
        download(assets[ASSET], archive)
        download(assets["checksums_sha256.txt"], checksums)
        expected = next(line.split()[0] for line in checksums.read_text().splitlines() if line.rstrip().endswith(ASSET))
        actual = hashlib.sha256(archive.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"F1DB checksum mismatch: expected {expected}, got {actual}")
        with zipfile.ZipFile(archive) as bundle:
            member = next(name for name in bundle.namelist() if name.endswith(".db"))
            bundle.extract(member, temp)
        database = temp / member
        staged_output = temp / "model-output.json"
        command = [sys.executable, "model/fit.py", "--database", str(database),
                   "--output", str(staged_output), "--artifact", str(args.data_dir / "posterior.nc"),
                   "--release", tag, "--method", args.method]
        subprocess.run(command, check=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged_output, args.output)
        args.output.chmod(0o644)
        database_target = args.data_dir / "f1db.db"
        os.replace(database, database_target)

    temporary_state = state_path.with_suffix(".tmp")
    temporary_state.write_text(json.dumps({"tag": tag, "sha256": actual}) + "\n")
    os.replace(temporary_state, state_path)
    print(f"Published model for {tag}")


if __name__ == "__main__":
    main()
