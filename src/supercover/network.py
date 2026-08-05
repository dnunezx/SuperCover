"""Small retrying HTTP client with bounded reads and cancellation."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .version import __version__


DEFAULT_MAX_BYTES = 8 * 1024 * 1024
READ_CHUNK_SIZE = 64 * 1024


class NetworkError(Exception):
    """A remote request failed after the configured retries."""


class HttpStatusError(NetworkError):
    """A server returned a non-success HTTP status."""

    def __init__(self, status: int, url: str):
        super().__init__(f"HTTP {status} for {url}")
        self.status = status
        self.url = url


class DownloadCancelled(NetworkError):
    """The caller cancelled an active request."""


@dataclass(frozen=True)
class HttpPayload:
    data: bytes
    content_type: str
    final_url: str


class HttpClient:
    """Dependency-free HTTP GET client suitable for a portable executable."""

    def __init__(
        self,
        *,
        timeout: float = 10.0,
        retries: int = 2,
        max_bytes: int = DEFAULT_MAX_BYTES,
        user_agent: str = f"SuperCover/{__version__} (+https://github.com/dnunezx/SuperCover)",
        cancelled: Callable[[], bool] | None = None,
        opener=None,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if retries < 0:
            raise ValueError("retries cannot be negative")
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self.timeout = timeout
        self.retries = retries
        self.max_bytes = max_bytes
        self.user_agent = user_agent
        self.cancelled = cancelled or (lambda: False)
        self.opener = opener or self._open
        self.sleeper = sleeper

    @staticmethod
    def _open(request: Request, timeout: float):
        return urlopen(request, timeout=timeout)

    def _check_cancelled(self) -> None:
        if self.cancelled():
            raise DownloadCancelled("download cancelled")

    def _read_response(self, response, url: str, max_bytes: int) -> HttpPayload:
        headers = response.headers
        content_length = headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > max_bytes:
                    raise NetworkError(f"response exceeds {max_bytes} bytes: {url}")
            except ValueError as exc:
                raise NetworkError(f"invalid Content-Length for {url}") from exc

        chunks: list[bytes] = []
        total = 0
        while True:
            self._check_cancelled()
            chunk = response.read(min(READ_CHUNK_SIZE, max_bytes - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise NetworkError(f"response exceeds {max_bytes} bytes: {url}")
            chunks.append(chunk)

        content_type = headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        final_url = response.geturl() if hasattr(response, "geturl") else url
        return HttpPayload(b"".join(chunks), content_type, final_url)

    def get(self, url: str, *, max_bytes: int | None = None) -> HttpPayload:
        """GET a bounded response, retrying temporary network/server failures."""

        limit = self.max_bytes if max_bytes is None else max_bytes
        if limit <= 0:
            raise ValueError("max_bytes must be positive")
        request = Request(url, headers={"User-Agent": self.user_agent, "Accept": "*/*"})
        last_error: Exception | None = None

        for attempt in range(self.retries + 1):
            self._check_cancelled()
            try:
                with self.opener(request, self.timeout) as response:
                    return self._read_response(response, url, limit)
            except DownloadCancelled:
                raise
            except HTTPError as exc:
                last_error = HttpStatusError(exc.code, url)
                retryable = exc.code == 429 or 500 <= exc.code <= 599
                if not retryable or attempt == self.retries:
                    raise last_error from exc
            except (URLError, TimeoutError, OSError) as exc:
                last_error = NetworkError(f"network request failed for {url}: {exc}")
                if attempt == self.retries:
                    raise last_error from exc

            self._check_cancelled()
            self.sleeper(0.25 * (2**attempt))

        raise NetworkError(f"network request failed for {url}") from last_error
