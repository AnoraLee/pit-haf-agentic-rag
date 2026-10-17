"""Research diagnostics must not confuse readiness with measured inference."""

import json
import subprocess
import urllib.error
import zipfile

import pytest

from pit_haf.research import doctor


@pytest.mark.parametrize("url", [
    "https://api.example.com", "http://127.0.0.1.evil.test:11434",
    "http://user:password@localhost:11434", "http://localhost:11434/path",
    "http://localhost:11434?model=x", "file:///tmp/ollama", "http://localhost:bad",
])
def test_diagnostic_never_calls_remote_or_credentialed_endpoint(url):
    with pytest.raises(ValueError):
        doctor.probe_ollama(url, "qwen3:4b")


def test_unavailable_ollama_is_reported_without_mock_inference(monkeypatch):
    def unavailable(url):
        raise urllib.error.URLError("Connection refused")
    monkeypatch.setattr(doctor, "read_json", unavailable)
    result = doctor.probe_ollama("http://127.0.0.1:11434", "qwen3:4b")
    assert result["status"] == "not_reachable"
    assert not result["ready_for_model_inspection"]
    assert result["inference_status"] == "not_measured"
    assert all(value["status"] == "error" for value in result["endpoints"].values())


def test_present_model_reports_digest_but_does_not_generate(monkeypatch):
    calls = []
    def read(url):
        calls.append(url)
        if url.endswith("/tags"):
            return {"models": [{"name": "qwen3:4b", "digest": "example-digest"}]}
        if url.endswith("/ps"):
            return {"models": []}
        return {"version": "example"}
    monkeypatch.setattr(doctor, "read_json", read)
    result = doctor.probe_ollama("http://localhost:11434/", "qwen3:4b")
    assert result["ready_for_model_inspection"]
    assert result["inference_status"] == "not_measured"
    assert len(calls) == 3
    assert not any("chat" in call or "generate" in call for call in calls)


def test_tag_similarity_is_not_accepted_as_same_model(monkeypatch):
    monkeypatch.setattr(doctor, "read_json", lambda url: {
        "models": [{"name": "qwen3:8b"}], "version": "example",
    })
    assert not doctor.probe_ollama("http://localhost:11434", "qwen3:4b")["candidate_present"]


def test_malformed_model_list_is_not_reported_ready(monkeypatch):
    monkeypatch.setattr(doctor, "read_json", lambda url: {"models": None})
    result = doctor.probe_ollama("http://localhost:11434", "qwen3:4b")
    assert not result["ready_for_model_inspection"]
    assert result["endpoints"]["tags"]["status"] == "error"


def test_source_snapshot_includes_untracked_source_and_dirty_diff(tmp_path):
    git = doctor.find_git()
    if git is None:
        pytest.skip("Git is unavailable on this host")
    root = tmp_path / "repo"
    root.mkdir()
    def run(*args):
        return subprocess.run([git, *args], cwd=root, check=True, capture_output=True)
    run("init")
    (root / "tracked.py").write_text("original\n")
    run("add", "tracked.py")
    run("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "initial")
    (root / "tracked.py").write_text("changed\n")
    (root / "new.py").write_text("untracked\n")
    output = tmp_path / "run"
    output.mkdir()
    result = doctor.capture_repository(root, output)
    assert result["status"] == "captured" and result["dirty"]
    assert result["captured_files"] == 2
    inventory = json.loads((output / "source_hashes.json").read_text())
    assert set(inventory) == {"tracked.py", "new.py"}
    with zipfile.ZipFile(output / "source_snapshot.zip") as archive:
        assert archive.read("new.py") == (root / "new.py").read_bytes()
    assert b"changed" in (output / "working-tree.patch").read_bytes()
    assert (root / "new.py").read_text() == "untracked\n"
