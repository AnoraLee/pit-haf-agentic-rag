"""Read-only local hardware/Ollama diagnostics; never downloads or runs a model."""

import argparse
import ctypes
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import urllib.error
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


def loopback_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Use a loopback Ollama URL without credentials, path or query.")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("Invalid Ollama port.") from exc
    return value.rstrip("/")


def read_json(url: str) -> dict:
    # Bypass HTTP proxies for local-only diagnostics.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=3) as response:
        result = json.load(response)
    if not isinstance(result, dict):
        raise ValueError("Expected an API JSON object.")
    return result


def probe_ollama(base_url: str, candidate: str) -> dict:
    base_url = loopback_url(base_url)
    result = {
        "base_url": base_url,
        "candidate": candidate,
        "status": "not_reachable",
        "candidate_present": False,
        "inference_status": "not_measured",
        "endpoints": {},
    }
    for endpoint in ("version", "tags", "ps"):
        try:
            payload = read_json(f"{base_url}/api/{endpoint}")
            result["endpoints"][endpoint] = {"status": "ok", "response": payload}
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            result["endpoints"][endpoint] = {"status": "error", "error": str(exc)}
    version = result["endpoints"]["version"]
    tags = result["endpoints"]["tags"]
    if version["status"] == "ok":
        result["status"] = "reachable"
    if tags["status"] == "ok":
        models = tags["response"].get("models", [])
        if not isinstance(models, list) or any(not isinstance(model, dict) for model in models):
            result["endpoints"]["tags"] = {"status": "error", "error": "Invalid model list."}
        else:
            result["candidate_present"] = any(
                model.get("name") == candidate or model.get("model") == candidate
                for model in models
            )
    result["ready_for_model_inspection"] = (
        result["status"] == "reachable" and result["candidate_present"]
    )
    return result


def hardware_report(disk_path: Path | None = None) -> dict:
    result = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "logical_cpus": os.cpu_count(),
        "processor": platform.processor(),
        "ram": {"status": "not_measured"},
        "gpu": {"status": "not_measured"},
    }
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                ("total_physical", ctypes.c_ulonglong), ("available_physical", ctypes.c_ulonglong),
                ("total_pagefile", ctypes.c_ulonglong), ("available_pagefile", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong), ("available_virtual", ctypes.c_ulonglong),
                ("available_extended_virtual", ctypes.c_ulonglong),
            ]

        memory = MemoryStatus()
        memory.length = ctypes.sizeof(memory)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            result["ram"] = {
                "status": "measured", "total_bytes": memory.total_physical,
                "available_bytes": memory.available_physical,
            }
    executable = shutil.which("nvidia-smi")
    if executable is None and os.name == "nt":
        candidate = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/nvidia-smi.exe"
        if candidate.is_file():
            executable = str(candidate)
    if executable:
        try:
            output = subprocess.run(
                [executable, "--query-gpu=name,memory.total,memory.free,driver_version",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5, check=True,
            ).stdout.strip()
            result["gpu"] = {"status": "measured", "query_output": output,
                             "memory_unit": "MiB"}
        except (OSError, subprocess.SubprocessError) as exc:
            result["gpu"] = {"status": "error", "error": str(exc)}
    queried_path = (disk_path or Path.cwd()).resolve()
    usage = shutil.disk_usage(queried_path)
    result["disk"] = {
        "queried_path": str(queried_path), "total_bytes": usage.total, "free_bytes": usage.free,
    }
    return result


def find_git() -> str | None:
    executable = shutil.which("git")
    if executable:
        return executable
    runtime_git = (
        Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe"
    )
    return str(runtime_git) if runtime_git.is_file() else None


def capture_repository(root: Path, destination: Path) -> dict:
    """Capture dirty source, including untracked files, without modifying Git."""
    git = find_git()
    if git is None:
        return {"status": "unavailable", "reason": "git executable not found"}

    def run(*args: str) -> bytes:
        return subprocess.check_output([git, *args], cwd=root, stderr=subprocess.PIPE, timeout=15)

    try:
        revision = run("rev-parse", "HEAD").decode().strip()
        status = run("status", "--porcelain=v1", "-z")
        patch = run("diff", "--binary", "--no-ext-diff", "HEAD")
        paths = run("ls-files", "--cached", "--others", "--exclude-standard", "-z")
        inventory = {}
        with zipfile.ZipFile(destination / "source_snapshot.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(set(paths.decode("utf-8").split("\0"))):
                if not name:
                    continue
                relative = Path(name)
                if (
                    relative.is_absolute() or ".." in relative.parts
                    or relative.parts[0] in {".git", ".aws", ".codex", ".agents", "outputs", ".venv"}
                    or relative.name == ".env" or relative.name == "secrets.toml"
                ):
                    continue
                path = root / relative
                if not path.is_file() or path.is_symlink():
                    continue
                data = path.read_bytes()
                inventory[relative.as_posix()] = hashlib.sha256(data).hexdigest()
                archive.writestr(relative.as_posix(), data)
        serialized = json.dumps(inventory, sort_keys=True).encode()
        (destination / "working-tree.patch").write_bytes(patch)
        (destination / "git-status.bin").write_bytes(status)
        (destination / "source_hashes.json").write_text(
            json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return {
            "status": "captured", "revision": revision, "dirty": bool(status),
            "working_tree_hash": hashlib.sha256(serialized).hexdigest(),
            "patch_sha256": hashlib.sha256(patch).hexdigest(),
            "snapshot_sha256": hashlib.sha256((destination / "source_snapshot.zip").read_bytes()).hexdigest(),
            "captured_files": len(inventory),
        }
    except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
        return {"status": "error", "reason": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/preflight"))
    parser.add_argument("--require-model", action="store_true")
    args = parser.parse_args()
    try:
        base_url = loopback_url(args.ollama_url)
    except ValueError as exc:
        parser.error(str(exc))
    root = Path(__file__).resolve().parents[3]
    output_base = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    destination = output_base / run_id
    destination.mkdir(parents=True, exist_ok=False)
    packages = {}
    for name in ("numpy", "pandas", "vnstock", "streamlit", "pydantic", "ollama", "pytest", "ruff"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    report = {
        "run_id": run_id, "run_kind": "environment_audit",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "hardware": hardware_report(root), "packages": packages,
        "ollama": probe_ollama(base_url, args.model),
        "repository": capture_repository(root, destination),
        "research_results": False,
        "next_step": "Inspect model digest and run a real-document pilot; no inference was performed.",
    }
    path = destination / "preflight.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report: {path}")
    print(f"Ollama: {report['ollama']['status']}; candidate present: {report['ollama']['candidate_present']}")
    print("Inference: NOT MEASURED. This report contains no prediction or research metrics.")
    if args.require_model and not report["ollama"]["ready_for_model_inspection"]:
        parser.exit(2, "Local model is not ready for inspection. See preflight.json.\n")


if __name__ == "__main__":
    main()
