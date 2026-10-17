"""Auditable loopback-only Ollama adapter (no downloads or cloud fallback).

API contracts: https://docs.ollama.com/api/chat and
https://docs.ollama.com/capabilities/structured-outputs .
The timeout is a socket timeout; a timed-out server request may still be running,
so timeout failures are deliberately not retried automatically.
"""

import hashlib
import http.client
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from pit_haf.research.doctor import loopback_url


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class OllamaConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen3:4b"
    num_ctx: Literal[2048, 4096] = 2048
    num_predict: int = Field(default=512, ge=1, le=1024)
    temperature: Literal[0] = 0
    seed: int = 42
    think: Literal[False] = False
    timeout_seconds: float = Field(default=180.0, ge=1, le=600)
    max_retries: int = Field(default=1, ge=0, le=1)
    keep_alive: str = "5m"

    @field_validator("base_url")
    @classmethod
    def local_endpoint(cls, value: str) -> str:
        return loopback_url(value)

    @field_validator("model")
    @classmethod
    def local_model_name(cls, value: str) -> str:
        if not value.strip() or "cloud" in value.lower() or "/" in value:
            raise ValueError("Use an installed local model tag, without cloud routing.")
        return value


class Extraction(BaseModel):
    """Summary support still requires semantic/human assessment."""

    model_config = ConfigDict(extra="forbid", strict=True)
    quote: str = Field(max_length=12000)
    extracted_numbers: list[str] = Field(max_length=100)
    summary: str = Field(max_length=4000)
    insufficient_evidence: bool


@dataclass(frozen=True)
class HttpReply:
    status: int
    body: bytes
    headers: dict[str, str]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_request(url: str, payload: bytes | None, timeout: float) -> HttpReply:
    """No proxy, no redirects, bounded response size, retain HTTP error bodies."""
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        body = response.read(4 * 1024 * 1024 + 1)
        if len(body) > 4 * 1024 * 1024:
            raise ValueError("Ollama response exceeds the 4 MiB audit limit.")
        return HttpReply(response.status, body, dict(response.headers.items()))


def _json_object(body: bytes) -> dict:
    value = json.loads(body)
    if not isinstance(value, dict):
        raise ValueError("Expected an API JSON object.")
    return value


class ModelInspectionError(RuntimeError):
    pass


class OllamaAdapter:
    """One sequential call at a time; failures are outputs, never synthetic answers."""

    def __init__(self, config: OllamaConfig, transport=None):
        self.config = config
        self.transport = transport or http_request

    def inspect(self, destination: Path) -> dict:
        destination.mkdir(parents=True, exist_ok=False)
        outputs = {}
        for endpoint, payload in (
            ("version", None), ("tags", None), ("ps", None),
            ("show", {"model": self.config.model, "verbose": False}),
        ):
            request = None if payload is None else json.dumps(payload).encode()
            (destination / f"{endpoint}.request.json").write_bytes(request or b"null")
            try:
                reply = self.transport(
                    f"{self.config.base_url}/api/{endpoint}", request,
                    min(self.config.timeout_seconds, 15.0),
                )
                (destination / f"{endpoint}.response.raw").write_bytes(reply.body)
                write_json(destination / f"{endpoint}.http.json", {
                    "status": reply.status, "headers": reply.headers,
                })
                if reply.status != 200:
                    raise ValueError(f"HTTP {reply.status}")
                outputs[endpoint] = _json_object(reply.body)
            except (OSError, ValueError, urllib.error.URLError, http.client.HTTPException) as exc:
                write_json(destination / "failure.json", {
                    "endpoint": endpoint, "error_type": type(exc).__name__, "error": str(exc),
                })
                raise ModelInspectionError(f"Model inspection failed at {endpoint}: {exc}") from exc
        models = outputs["tags"].get("models")
        candidates = [item for item in models if isinstance(item, dict) and (
            item.get("name") == self.config.model or item.get("model") == self.config.model
        )] if isinstance(models, list) else []
        if len(candidates) != 1 or not isinstance(candidates[0].get("digest"), str):
            raise ModelInspectionError("Exactly one installed local model with a digest is required.")
        digest = candidates[0]["digest"]
        if not re.fullmatch(r"(?:sha256:)?[a-fA-F0-9]{64}", digest):
            raise ModelInspectionError("Installed model digest is not a full SHA-256 digest.")
        show = outputs["show"]
        if show.get("remote_host") or show.get("remote_model"):
            raise ModelInspectionError("Remote-backed models are not allowed by this local adapter.")
        version = outputs["version"].get("version")
        if not isinstance(version, str) or not version:
            raise ModelInspectionError("Missing Ollama server version.")
        result = {
            "model": self.config.model, "digest": digest, "server_version": version,
            "tag_details": candidates[0], "show": show, "placement": outputs["ps"],
            "source": "local_api", "training_cutoff": "unknown",
        }
        write_json(destination / "inspection.json", result)
        return result

    def extract(self, messages: list[dict[str, str]], destination: Path) -> dict:
        destination.mkdir(parents=True, exist_ok=False)
        request = {
            "model": self.config.model, "messages": messages,
            "format": Extraction.model_json_schema(), "stream": False,
            "think": self.config.think, "keep_alive": self.config.keep_alive,
            "options": {"num_ctx": self.config.num_ctx, "num_predict": self.config.num_predict,
                        "temperature": self.config.temperature, "seed": self.config.seed},
        }
        payload = json.dumps(request, ensure_ascii=False).encode("utf-8")
        attempts = []
        output = None
        for index in range(self.config.max_retries + 1):
            attempt_dir = destination / f"attempt-{index + 1:02d}"
            attempt_dir.mkdir()
            (attempt_dir / "request.json").write_bytes(payload)
            started = time.perf_counter()
            attempt = {
                "attempt": index + 1, "created_at": datetime.now(timezone.utc).isoformat(),
                "request_sha256": sha256(payload), "status": "failed", "retryable": False,
                "usage": None,
            }
            try:
                reply = self.transport(
                    f"{self.config.base_url}/api/chat", payload, self.config.timeout_seconds,
                )
                (attempt_dir / "response.raw").write_bytes(reply.body)
                attempt.update({"http_status": reply.status, "response_sha256": sha256(reply.body),
                                "response_headers": reply.headers})
                if reply.status != 200:
                    message = reply.body.decode("utf-8", errors="replace")
                    oom = any(term in message.lower() for term in (
                        "out of memory", "not enough memory", "insufficient memory", "cuda malloc",
                        "requires more system memory", "unable to allocate",
                    ))
                    attempt.update({"failure": "oom" if oom else "http_error", "error": message,
                                    "retryable": not oom and reply.status in {429, 500, 502, 503, 504}})
                else:
                    try:
                        result = _json_object(reply.body)
                    except (ValueError, UnicodeError) as exc:
                        attempt.update({"failure": "api_invalid_json", "error": str(exc),
                                        "retryable": True})
                    else:
                        attempt["usage"] = {key: result.get(key) for key in (
                            "prompt_eval_count", "eval_count", "total_duration", "load_duration",
                            "prompt_eval_duration", "eval_duration",
                        )}
                        if result.get("error"):
                            error = str(result["error"])
                            oom = "memory" in error.lower() or "cuda malloc" in error.lower()
                            attempt.update({"failure": "oom" if oom else "api_error", "error": error})
                        elif result.get("done") is not True or result.get("done_reason") == "length":
                            attempt.update({"failure": "incomplete_generation", "error": result.get(
                                "done_reason", "missing done=true"), "retryable": True})
                        else:
                            message = result.get("message")
                            content = message.get("content") if isinstance(message, dict) else None
                            if not isinstance(content, str):
                                attempt.update({"failure": "missing_content", "retryable": True})
                            else:
                                (attempt_dir / "content.txt").write_text(content, encoding="utf-8")
                                try:
                                    parsed = json.loads(content)
                                except ValueError as exc:
                                    attempt.update({"failure": "content_invalid_json", "error": str(exc),
                                                    "retryable": True})
                                else:
                                    try:
                                        output = Extraction.model_validate(parsed)
                                    except ValidationError as exc:
                                        attempt.update({"failure": "schema_validation", "error": str(exc),
                                                        "retryable": True})
                                    else:
                                        attempt["status"] = "schema_valid"
            except (TimeoutError, urllib.error.URLError, OSError, ValueError,
                    http.client.HTTPException) as exc:
                if isinstance(getattr(exc, "partial", None), bytes):
                    (attempt_dir / "response.partial.raw").write_bytes(exc.partial)
                timed_out = isinstance(exc, TimeoutError) or isinstance(
                    getattr(exc, "reason", None), TimeoutError,
                )
                attempt.update({
                    "failure": "timeout" if timed_out else "transport_error", "error": str(exc),
                    "error_type": type(exc).__name__, "retryable": not timed_out,
                    "server_cancellation": "unconfirmed" if timed_out else None,
                })
            attempt["wall_seconds"] = time.perf_counter() - started
            write_json(attempt_dir / "attempt.json", attempt)
            attempts.append(attempt)
            if output is not None or not attempt["retryable"]:
                break
        result = {
            "status": "schema_valid" if output is not None else "failed",
            "output": output.model_dump() if output is not None else None,
            "attempts": attempts, "attempt_count": len(attempts),
            "wall_seconds": sum(item["wall_seconds"] for item in attempts),
            "timeout_semantics": "socket timeout; cancellation unconfirmed; no automatic timeout retry",
            "request_sha256": sha256(payload),
        }
        write_json(destination / "result.json", result)
        return result
