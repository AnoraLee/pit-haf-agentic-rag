"""Pinned download failures are checked offline; no external network calls."""

import hashlib

import pytest

from pit_haf.data.hub import fetch_file


@pytest.mark.parametrize("path", ["../escape.csv", "/absolute.csv", "C:/escape.csv", "x\\escape.csv"])
def test_dataset_download_rejects_escaping_paths(tmp_path, path):
    with pytest.raises(ValueError, match="relative path"):
        fetch_file("synthetic/news", "a" * 40, {"path": path, "size": 3, "sha256": "a" * 64}, tmp_path)


def test_local_pinned_download_reuse_checks_exact_bytes(tmp_path, monkeypatch):
    path = tmp_path / "fixture.csv"
    path.write_bytes(b"synthetic fixture")
    spec = {"path": path.name, "size": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: pytest.fail("Local verified reuse attempted HTTP"))
    assert fetch_file("synthetic/news", "a" * 40, spec, tmp_path)["status"] == "verified_local_reuse"
    path.write_bytes(b"changed fixture!!")
    with pytest.raises(ValueError, match="integrity"):
        fetch_file("synthetic/news", "a" * 40, spec, tmp_path)
