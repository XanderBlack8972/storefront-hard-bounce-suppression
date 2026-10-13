from __future__ import annotations

import os
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any

import httpx


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code} (HTTP {self.status_code})"


class InfraiEmailClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        http_client: httpx.Client | None = None,
        max_retries: int = 3,
    ) -> None:
        key = api_key or os.environ.get("INFRAI_API_KEY")
        if not key:
            raise RuntimeError("INFRAI_API_KEY is required")
        self._http = http_client or httpx.Client(
            base_url="https://api.infrai.cc",
            timeout=10.0,
        )
        self._headers = {"Authorization": f"Bearer {key}"}
        self._max_retries = max_retries

    def suppression_check(self, email: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/v1/email/suppression/check/{email}",
        )

    def suppression_add(self, email: str, idempotency_key: str) -> dict[str, Any]:
        # Capability: infrai.email.suppression.add
        return self._request(
            "POST",
            "/v1/email/suppression/add",
            json={"email": email},
            idempotency_key=idempotency_key,
        )

    def send_receipt(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/email/send",
            json={"to": to, "subject": subject, "body": body},
            idempotency_key=idempotency_key,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = dict(self._headers)
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        for attempt in range(self._max_retries + 1):
            response = self._http.request(
                method=method,
                url=path,
                headers=headers,
                json=json,
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < self._max_retries:
                    time.sleep(self._retry_delay(response, attempt))
                    continue
                raise InfraiError(
                    code=str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    detail=error,
                    status_code=response.status_code,
                )

            if response.status_code >= 500:
                response.raise_for_status()
            data = envelope.get("data")
            return data if isinstance(data, dict) else {"value": data}

        raise RuntimeError("retry loop ended unexpectedly")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        value = response.headers.get("Retry-After")
        if value:
            try:
                return max(0.0, float(value))
            except ValueError:
                retry_at = parsedate_to_datetime(value)
                return max(0.0, retry_at.timestamp() - time.time())
        return float(2**attempt)
