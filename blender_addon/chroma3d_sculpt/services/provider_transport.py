"""Bounded synchronous HTTPS transport with no redirects, cookies or retries."""

from __future__ import annotations

from dataclasses import dataclass, field
import http.client
import ssl
import threading
from typing import Mapping

from ..models.ai_assistance_models import FailureClass


ALLOWED_HTTPS_HOSTS = frozenset({"api.openai.com"})


class TransportError(RuntimeError):
    def __init__(self, failure_class: FailureClass, safe_message: str, *, status_code: int | None = None) -> None:
        super().__init__(safe_message)
        self.failure_class = failure_class
        self.safe_message = safe_message
        self.status_code = status_code


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise TransportError(FailureClass.CANCELLED, "The provider request was cancelled.")


@dataclass(frozen=True, slots=True)
class TransportRequest:
    host: str
    path: str
    body: bytes
    headers: Mapping[str, str]
    timeout_seconds: float
    maximum_response_bytes: int
    method: str = "POST"

    def __post_init__(self) -> None:
        if self.host not in ALLOWED_HTTPS_HOSTS:
            raise ValueError("Provider host is not allow-listed.")
        if not self.path.startswith("/") or ".." in self.path.split("/") or "://" in self.path:
            raise ValueError("Provider path is invalid.")
        if self.method != "POST":
            raise ValueError("Only POST provider requests are allowed.")
        if isinstance(self.timeout_seconds, bool) or not 0 < float(self.timeout_seconds) <= 180:
            raise ValueError("Transport timeout is outside the bounded policy.")
        if isinstance(self.maximum_response_bytes, bool) or not 1 <= self.maximum_response_bytes <= 1_048_576:
            raise ValueError("Transport response limit is outside the bounded policy.")
        if len(self.body) > 1_048_576:
            raise ValueError("Transport request body exceeds the compiled maximum.")
        lowered = {str(key).lower() for key in self.headers}
        if "cookie" in lowered:
            raise ValueError("Provider requests may not contain cookies.")


@dataclass(frozen=True, slots=True)
class TransportResponse:
    status_code: int
    body: bytes
    content_type: str
    request_id: str = ""
    headers: Mapping[str, str] = field(default_factory=dict)


class HTTPSProviderTransport:
    """One-shot standard-library HTTPS transport.

    ``http.client`` intentionally does not follow redirects and does not retain a
    connection/session, cookies, or proxy credentials.
    """

    def send(self, request: TransportRequest, *, cancellation: CancellationToken | None = None) -> TransportResponse:
        token = cancellation or CancellationToken()
        token.raise_if_cancelled()
        connection = http.client.HTTPSConnection(
            request.host,
            timeout=float(request.timeout_seconds),
            context=ssl.create_default_context(),
        )
        try:
            connection.request(request.method, request.path, body=request.body, headers=dict(request.headers))
            token.raise_if_cancelled()
            response = connection.getresponse()
            if 300 <= response.status < 400:
                raise TransportError(FailureClass.TRANSPORT, "Provider redirects are not allowed.", status_code=response.status)
            if not 200 <= response.status < 300:
                raise TransportError(FailureClass.PROVIDER, f"Provider returned HTTP {response.status}.", status_code=response.status)
            content_type = str(response.getheader("Content-Type", "")).split(";", 1)[0].strip().lower()
            if content_type not in {"application/json", "application/problem+json"}:
                raise TransportError(FailureClass.CONTENT_TYPE, "Provider response content type is not JSON.", status_code=response.status)
            content_length = response.getheader("Content-Length")
            if content_length:
                try:
                    declared = int(content_length)
                except ValueError as exc:
                    raise TransportError(FailureClass.RESPONSE_LIMIT, "Provider returned an invalid response length.") from exc
                if declared > request.maximum_response_bytes:
                    raise TransportError(FailureClass.RESPONSE_LIMIT, "Provider response exceeds the configured size limit.")
            body = response.read(request.maximum_response_bytes + 1)
            if len(body) > request.maximum_response_bytes:
                raise TransportError(FailureClass.RESPONSE_LIMIT, "Provider response exceeds the configured size limit.")
            token.raise_if_cancelled()
            selected_headers = {
                "x-request-id": str(response.getheader("x-request-id", ""))[:512],
                "openai-processing-ms": str(response.getheader("openai-processing-ms", ""))[:64],
            }
            return TransportResponse(
                status_code=response.status,
                body=body,
                content_type=content_type,
                request_id=selected_headers["x-request-id"],
                headers=selected_headers,
            )
        except TransportError:
            raise
        except TimeoutError as exc:
            raise TransportError(FailureClass.TIMEOUT, "The provider request timed out.") from exc
        except (ssl.SSLError, http.client.HTTPException, OSError) as exc:
            raise TransportError(FailureClass.TRANSPORT, f"Provider transport failed ({type(exc).__name__}).") from exc
        finally:
            connection.close()


__all__ = (
    "ALLOWED_HTTPS_HOSTS", "CancellationToken", "HTTPSProviderTransport", "TransportError",
    "TransportRequest", "TransportResponse",
)
