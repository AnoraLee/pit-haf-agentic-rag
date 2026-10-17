"""Transport fixtures test failure handling; no model/research results are simulated."""

import json
import urllib.error

import pytest
from pydantic import ValidationError

from pit_haf.llm.ollama import HttpReply, ModelInspectionError, OllamaAdapter, OllamaConfig


def reply(value, status=200):
    return HttpReply(status, json.dumps(value).encode(), {})


def completion(content=None, **kwargs):
    if content is None:
        content = json.dumps({"quote": "Doanh thu 12 tỷ đồng.", "extracted_numbers": ["12 tỷ đồng"],
                              "summary": "Doanh thu đạt 12 tỷ đồng.", "insufficient_evidence": False})
    return reply({"done": True, "message": {"role": "assistant", "content": content},
                  "eval_count": 21, "prompt_eval_count": 100, **kwargs})


@pytest.mark.parametrize("settings", [
    {"base_url": "https://remote.example"}, {"base_url": "http://u:p@localhost:11434"},
    {"base_url": "http://localhost:11434/path"}, {"base_url": "http://localhost:bad"},
    {"model": "qwen3:cloud"}, {"max_retries": 2}, {"num_ctx": 8192}, {"think": True},
    {"temperature": 1}, {"timeout_seconds": 0.0},
])
def test_invalid_or_remote_configuration_is_rejected(settings):
    with pytest.raises(ValidationError):
        OllamaConfig(**settings)


def test_success_retains_exact_payload_raw_response_schema_and_usage(tmp_path):
    calls = []
    response = completion()
    def transport(url, payload, timeout):
        calls.append((url, payload, timeout))
        return response
    result = OllamaAdapter(OllamaConfig(), transport).extract(
        [{"role": "user", "content": "test"}], tmp_path / "call",
    )
    request = json.loads(calls[0][1])
    assert request["stream"] is False and request["think"] is False
    assert request["options"] == {"num_ctx": 2048, "num_predict": 512, "temperature": 0, "seed": 42}
    assert request["format"]["additionalProperties"] is False
    assert result["status"] == "schema_valid" and result["attempt_count"] == 1
    assert result["attempts"][0]["usage"]["eval_count"] == 21
    attempt = tmp_path / "call/attempt-01"
    assert (attempt / "response.raw").read_bytes() == response.body
    assert (attempt / "request.json").read_bytes() == calls[0][1]
    assert "Doanh thu" in (attempt / "content.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize("bad,kind", [
    (HttpReply(200, b"not-json", {}), "api_invalid_json"),
    (completion("```json\n{}\n```"), "content_invalid_json"),
    (completion('{"quote": 123}'), "schema_validation"),
    (completion("{}", done_reason="length"), "incomplete_generation"),
    (reply({"done": True}), "missing_content"),
])
def test_invalid_output_keeps_failed_attempt_and_bounded_retry(tmp_path, bad, kind):
    calls = []
    def transport(*args):
        calls.append(args)
        return bad if len(calls) == 1 else completion()
    result = OllamaAdapter(OllamaConfig(), transport).extract([], tmp_path / "call")
    assert result["status"] == "schema_valid" and len(calls) == 2
    assert result["attempts"][0]["failure"] == kind
    assert (tmp_path / "call/attempt-01/response.raw").read_bytes() == bad.body
    assert (tmp_path / "call/attempt-02/response.raw").is_file()


def test_oom_has_no_silent_fallback_or_retry(tmp_path):
    calls = []
    def transport(*args):
        calls.append(args)
        return reply({"error": "model requires more memory: out of memory"}, 500)
    result = OllamaAdapter(OllamaConfig(), transport).extract([], tmp_path / "call")
    assert result["output"] is None and result["attempt_count"] == 1
    assert result["attempts"][0]["failure"] == "oom"
    assert json.loads(calls[0][1])["model"] == "qwen3:4b"


def test_timeout_is_not_retried_when_server_cancellation_is_unknown(tmp_path):
    def transport(url, payload, timeout):
        assert timeout == 1.0
        raise urllib.error.URLError(TimeoutError("timed out"))
    result = OllamaAdapter(OllamaConfig(timeout_seconds=1.0), transport).extract([], tmp_path / "call")
    assert result["attempt_count"] == 1 and result["output"] is None
    attempt = result["attempts"][0]
    assert attempt["failure"] == "timeout" and attempt["server_cancellation"] == "unconfirmed"
    assert (tmp_path / "call/attempt-01/attempt.json").is_file()


def test_transport_retry_is_finite_and_records_every_failure(tmp_path):
    def transport(*args):
        raise urllib.error.URLError("connection refused")
    result = OllamaAdapter(OllamaConfig(), transport).extract([], tmp_path / "call")
    assert result["attempt_count"] == 2 and result["output"] is None
    assert all(item["failure"] == "transport_error" for item in result["attempts"])


def test_http_client_does_not_follow_redirect_to_remote_host(monkeypatch):
    from pit_haf.llm import ollama
    calls = []
    class RedirectReply:
        status = 302
        headers = {"Location": "https://remote.example"}
        def read(self, limit):
            return b"redirect"
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url)
            return RedirectReply()
    handlers = []
    def build(*args):
        handlers.extend(args)
        return Opener()
    monkeypatch.setattr(ollama.urllib.request, "build_opener", build)
    result = ollama.http_request("http://localhost:11434/api/chat", b"{}", 1)
    assert result.status == 302 and len(calls) == 1
    redirect = next(item for item in handlers if isinstance(item, ollama.NoRedirect))
    assert redirect.redirect_request(None, None, 302, "", {}, "https://remote.example") is None


def test_inspection_requires_exact_tag_and_full_digest_and_saves_metadata(tmp_path):
    digest = "a" * 64
    def transport(url, payload, timeout):
        if url.endswith("version"):
            return reply({"version": "fixture-version"})
        if url.endswith("tags"):
            return reply({"models": [{"name": "qwen3:4b", "digest": digest,
                                       "details": {"quantization_level": "Q4_K_M"}}]})
        if url.endswith("ps"):
            return reply({"models": []})
        assert json.loads(payload)["model"] == "qwen3:4b"
        return reply({"details": {"parameter_size": "4B"}, "capabilities": ["completion", "thinking"]})
    result = OllamaAdapter(OllamaConfig(), transport).inspect(tmp_path / "inspect")
    assert result["digest"] == digest and result["training_cutoff"] == "unknown"
    assert (tmp_path / "inspect/show.response.raw").is_file()


@pytest.mark.parametrize("models,show", [
    ([{"name": "qwen3:8b", "digest": "a" * 64}], {}),
    ([{"name": "qwen3:4b", "digest": "short"}], {}),
    ([{"name": "qwen3:4b", "digest": "a" * 64}], {"remote_host": "https://remote.example"}),
])
def test_inspection_rejects_missing_wrong_or_remote_model(tmp_path, models, show):
    def transport(url, payload, timeout):
        return reply({"models": models} if url.endswith("tags") else
                     {"version": "fixture"} if url.endswith("version") else show)
    with pytest.raises(ModelInspectionError):
        OllamaAdapter(OllamaConfig(), transport).inspect(tmp_path / "inspect")
