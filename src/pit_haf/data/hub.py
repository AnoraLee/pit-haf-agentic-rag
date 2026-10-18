"""Bounded, pinned public dataset downloads; never execute repository code."""

import argparse
import hashlib
import json
import re
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlsplit


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_file(repo: str, revision: str, spec: dict, root: Path) -> dict:
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Use an explicit public repository and pinned 40-character revision")
    relative = PurePosixPath(spec["path"])
    if relative.is_absolute() or ".." in relative.parts or "\\" in spec["path"] or any(":" in part for part in relative.parts):
        raise ValueError("Invalid dataset relative path")
    limit = spec["size"]
    if not 0 < limit <= 2 * 1024 ** 3 or not re.fullmatch(r"[0-9a-f]{64}", spec["sha256"]):
        raise ValueError("Dataset file requires a bounded size and SHA-256")
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.stat().st_size != limit or file_sha(target) != spec["sha256"]:
            raise ValueError("Existing pinned dataset file failed integrity check")
        return {**spec, "status": "verified_local_reuse", "path_local": str(target.resolve())}
    url = f"https://huggingface.co/datasets/{repo}/resolve/{revision}/{quote(str(relative))}?download=true"
    partial = target.with_suffix(target.suffix + ".part")
    for attempt in range(3):
        offset = partial.stat().st_size if partial.exists() else 0
        request = urllib.request.Request(url, headers={
            "User-Agent": "PiT-HAF/0.5 public-academic-dataset-import",
            **({"Range": f"bytes={offset}-"} if offset else {})})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                host = urlsplit(response.url).hostname or ""
                if not (host == "huggingface.co" or host.endswith(".huggingface.co") or host.endswith(".hf.co")):
                    raise ValueError("Unexpected dataset download redirect")
                if response.status == 206:
                    if not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                        raise ValueError("Dataset resume range does not match local bytes")
                elif response.status == 200:
                    offset = 0
                else:
                    raise ValueError("Unexpected dataset download status")
                count, reported = offset, offset
                with partial.open("ab" if offset else "wb") as stream:
                    while chunk := response.read(1024 * 1024):
                        count += len(chunk)
                        if count > limit:
                            raise ValueError("Dataset file exceeds pinned byte limit")
                        stream.write(chunk)
                        if count - reported >= 64 * 1024 * 1024:
                            print(json.dumps({"file": spec["path"], "bytes": count, "total": limit}), flush=True)
                            reported = count
            if partial.stat().st_size != limit or file_sha(partial) != spec["sha256"]:
                raise ValueError("Downloaded dataset file checksum/size mismatch")
            partial.replace(target)
            return {**spec, "status": "downloaded_and_verified", "source_url": url,
                    "retrieved_at": datetime.now(UTC).isoformat(), "path_local": str(target.resolve())}
        except (OSError, TimeoutError) as exc:
            if getattr(exc, "code", None) in {401, 403, 429} or attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("Unreachable download state")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--file", action="append", default=[])
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    for spec in config["files"]:
        if args.file and spec["path"] not in args.file:
            continue
        result = fetch_file(config["dataset_id"], config["dataset_revision"], spec, args.root)
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
