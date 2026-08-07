"""Bounded standard-library HTTP transport for explicitly authorized CGB jobs."""

from __future__ import annotations

from abc import abstractmethod
from decimal import Decimal
import json
import mimetypes
import os
from pathlib import Path
import time
from typing import Any, Mapping
from urllib import error, parse, request
from uuid import uuid4

from .base import (
    BenchmarkPolicyError,
    CostEstimate,
    GenerationBackend,
    GenerationJob,
    GenerationRequest,
    redact_sensitive,
)


class RemoteGenerationBackend(GenerationBackend):
    credential_env = ""
    base_url = ""
    maximum_response_bytes = 2 * 1024 * 1024
    maximum_artifact_bytes = 512 * 1024 * 1024
    request_timeout_seconds = 30
    maximum_retries = 1

    def credential_present(self) -> bool:
        return bool(self.credential_env and os.environ.get(self.credential_env))

    def validate_environment(self) -> dict[str, Any]:
        if not self.policy.allow_live_provider_calls or self.policy.max_live_jobs == 0 or self.policy.max_spend_usd == 0:
            state = "SPEND_NOT_AUTHORIZED"
        elif not self.credential_present():
            state = "MISSING_CREDENTIAL"
        else:
            state = "READY_REMOTE"
        return {
            **self.base_environment(), "availability_state": state,
            "credential_present": self.credential_present(), "credential_value_disclosed": False,
            "live_calls_allowed": self.policy.allow_live_provider_calls,
        }

    def _credential(self) -> str:
        value = os.environ.get(self.credential_env, "")
        if not value:
            raise BenchmarkPolicyError("MISSING_CREDENTIAL", f"{self.credential_env} is not configured.")
        return value

    def _authorize(self, estimate: CostEstimate) -> None:
        self.policy.authorize_live_stage(jobs=1, estimate=estimate)
        self._credential()

    def _headers(self, *, json_body: bool = True) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._credential()}", "Accept": "application/json"}
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    def _request_json(
        self,
        method: str,
        url: str,
        payload: Mapping[str, Any] | None = None,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
        last_error: Exception | None = None
        for attempt in range(self.maximum_retries + 1):
            try:
                req = request.Request(url, data=body, method=method, headers=dict(headers or self._headers()))
                with request.urlopen(req, timeout=self.request_timeout_seconds) as response:
                    data = response.read(self.maximum_response_bytes + 1)
                    if len(data) > self.maximum_response_bytes:
                        raise RuntimeError("Provider response exceeded the bounded metadata limit.")
                    parsed = json.loads(data.decode("utf-8")) if data else {}
                    if not isinstance(parsed, dict):
                        raise RuntimeError("Provider response must be a JSON object.")
                    return parsed
            except (error.HTTPError, error.URLError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
                last_error = exc
                retryable = isinstance(exc, error.HTTPError) and exc.code in {429, 500, 502, 503, 504}
                if attempt >= self.maximum_retries or not retryable:
                    break
                time.sleep(min(2 ** attempt, 2))
        status = getattr(last_error, "code", None)
        raise RuntimeError(f"Provider request failed ({type(last_error).__name__}, status={status}).") from last_error

    def _multipart_request(
        self,
        url: str,
        fields: Mapping[str, str],
        files: tuple[tuple[str, Path], ...],
    ) -> dict[str, Any]:
        boundary = f"cgb-{uuid4().hex}"
        chunks: list[bytes] = []
        for name, value in fields.items():
            chunks.extend((
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n".encode(),
                value.encode("utf-8"), b"\r\n",
            ))
        for name, path in files:
            content = path.read_bytes()
            if len(content) > 32 * 1024 * 1024:
                raise ValueError("Reference upload exceeds the 32 MiB CGB request limit.")
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            chunks.extend((
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{path.name}\"\r\nContent-Type: {mime}\r\n\r\n".encode(),
                content, b"\r\n",
            ))
        chunks.append(f"--{boundary}--\r\n".encode())
        body = b"".join(chunks)
        headers = self._headers(json_body=False)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        req = request.Request(url, data=body, method="POST", headers=headers)
        try:
            with request.urlopen(req, timeout=self.request_timeout_seconds) as response:
                data = response.read(self.maximum_response_bytes + 1)
        except (error.HTTPError, error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"Provider multipart request failed ({type(exc).__name__}, status={getattr(exc, 'code', None)}).") from exc
        if len(data) > self.maximum_response_bytes:
            raise RuntimeError("Provider response exceeded the bounded metadata limit.")
        parsed = json.loads(data.decode("utf-8")) if data else {}
        if not isinstance(parsed, dict):
            raise RuntimeError("Provider response must be a JSON object.")
        return parsed

    def _download(self, url: str, target: Path) -> Path:
        parsed = parse.urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise RuntimeError("Artifact URL must use HTTPS.")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".part")
        total = 0
        try:
            with request.urlopen(url, timeout=self.request_timeout_seconds) as response, temporary.open("wb") as stream:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > self.maximum_artifact_bytes:
                        raise RuntimeError("Provider artifact exceeded the 512 MiB CGB limit.")
                    stream.write(chunk)
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return target

    @abstractmethod
    def request_preview(self, request_value: GenerationRequest) -> Mapping[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def _submit_live(self, request_value: GenerationRequest) -> GenerationJob:
        raise NotImplementedError

    def submit(self, request_value: GenerationRequest, output_directory: Path) -> GenerationJob:
        request_value.validate()
        unsupported = self.unsupported_track_job(request_value)
        if unsupported is not None:
            return unsupported
        descriptor = self.backend_info()
        preview = redact_sensitive(self.request_preview(request_value))
        if request_value.dry_run:
            return GenerationJob(descriptor.backend_id, "dry-run", "PASS", request_value, {
                "dry_run": True, "network_calls": 0, "request_preview": preview,
                "environment": self.validate_environment(), "cost": self.estimate_cost(request_value).to_dict(),
            })
        self._authorize(self.estimate_cost(request_value))
        return self._submit_live(request_value)

    def poll(self, job: GenerationJob) -> GenerationJob:
        self._authorize(CostEstimate("KNOWN", Decimal("0"), Decimal("0"), "Polling has no generation charge"))
        return self._poll_live(job)

    def cancel(self, job: GenerationJob) -> GenerationJob:
        self._authorize(CostEstimate("KNOWN", Decimal("0"), Decimal("0"), "Cancellation has no generation charge"))
        return self._cancel_live(job)

    def retrieve(self, job: GenerationJob, output_directory: Path) -> GenerationJob:
        self._authorize(CostEstimate("KNOWN", Decimal("0"), Decimal("0"), "Retrieval has no generation charge"))
        return self._retrieve_live(job, output_directory)

    @abstractmethod
    def _poll_live(self, job: GenerationJob) -> GenerationJob:
        raise NotImplementedError

    @abstractmethod
    def _cancel_live(self, job: GenerationJob) -> GenerationJob:
        raise NotImplementedError

    @abstractmethod
    def _retrieve_live(self, job: GenerationJob, output_directory: Path) -> GenerationJob:
        raise NotImplementedError
