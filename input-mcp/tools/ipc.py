"""HTTP client used by the LLM-facing tools to talk to the UI service.

The client is self-healing: if a request fails with a connection error, it
calls back into bootstrap to re-spawn the UI service and retries once. This
matters because LM Studio's process model can kill child processes more
aggressively than a terminal shell does, leaving the MCP server alive but
its UI subprocess dead.
"""
from __future__ import annotations

from typing import Any, Callable

import httpx

from ._logging import get_logger

log = get_logger("ipc")


# Returned when something below the dialog layer prevented us from getting
# a real user answer. live: False is the signal to the LLM.
def _synthetic_failure(type_: str, reason: str, port: int | None = None) -> dict[str, Any]:
    return {
        "status": "cancelled",
        "live": False,
        "value": None,
        "user_note": "",
        "answered_at": None,
        "elapsed_ms": 0,
        "request_id": None,
        "type": type_,
        "error": reason,
        "ui_port": port,
        "hint": (
            "The popup UI service was not reachable. Check logs/mcp.log and "
            "logs/ui.log; run `uv run python scripts/kill_ui.py` to clear orphans, "
            "then restart input-mcp."
        ),
    }


class UIClient:
    def __init__(
        self,
        port: int,
        token: str,
        respawn_callback: Callable[[], tuple[int, str]] | None = None,
    ) -> None:
        self._port = port
        self._token = token
        self._base = f"http://127.0.0.1:{port}"
        self._respawn = respawn_callback

    @property
    def port(self) -> int:
        return self._port

    @property
    def token(self) -> str:
        return self._token

    def _rebind(self, port: int, token: str) -> None:
        self._port = port
        self._token = token
        self._base = f"http://127.0.0.1:{port}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def is_healthy(self, timeout: float = 1.5) -> bool:
        try:
            r = httpx.get(
                f"{self._base}/health",
                headers=self._headers(),
                timeout=timeout,
            )
            return r.status_code == 200 and bool(r.json().get("ok"))
        except Exception:
            return False

    def _maybe_respawn(self) -> bool:
        """Try to re-spawn the UI service. Returns True if we got a live UI."""
        if not self._respawn:
            return False
        try:
            new_port, new_token = self._respawn()
        except Exception as exc:  # noqa: BLE001
            log.error("respawn failed: %s", exc)
            return False
        self._rebind(new_port, new_token)
        log.info("ui respawned on port=%d (new token)", new_port)
        return self.is_healthy()

    def ask(self, type_: str, prompt: str, spec: dict[str, Any],
            timeout_sec: int, origin: str = "input-mcp") -> dict[str, Any]:
        timeout_sec = max(1, min(int(timeout_sec or 300), 3600))
        client_timeout = httpx.Timeout(timeout_sec + 60, connect=5.0)
        body = {
            "type": type_,
            "prompt": prompt,
            "spec": spec,
            "timeout_sec": timeout_sec,
            "origin": origin,
        }

        for attempt in (1, 2):
            try:
                r = httpx.post(
                    f"{self._base}/ask",
                    json=body,
                    headers=self._headers(),
                    timeout=client_timeout,
                )
            except (httpx.ConnectError, httpx.RemoteProtocolError) as exc:
                log.warning(
                    "ask connection failure (attempt %d) port=%d: %s",
                    attempt, self._port, exc,
                )
                if attempt == 1 and self._maybe_respawn():
                    continue
                return _synthetic_failure(
                    type_,
                    f"could not connect to UI service at 127.0.0.1:{self._port}: {exc}",
                    self._port,
                )
            except httpx.TimeoutException:
                log.warning("ask http timeout port=%d type=%s", self._port, type_)
                return _synthetic_failure(
                    type_, "client_timeout (UI did not respond in time)", self._port,
                )
            except httpx.HTTPError as exc:
                log.warning("ask http error port=%d: %s", self._port, exc)
                return _synthetic_failure(
                    type_, f"http_error:{type(exc).__name__}: {exc}", self._port,
                )

            if r.status_code == 401:
                log.warning("ask got 401 — token mismatch (attempt %d)", attempt)
                if attempt == 1 and self._maybe_respawn():
                    continue
                return _synthetic_failure(
                    type_, "unauthorized (token mismatch)", self._port,
                )
            if r.status_code != 200:
                log.warning("ask http %d: %s", r.status_code, r.text[:200])
                return _synthetic_failure(
                    type_, f"http_{r.status_code}: {r.text[:120]}", self._port,
                )
            try:
                return r.json()
            except Exception as exc:  # noqa: BLE001
                log.warning("ask response not JSON: %s", exc)
                return _synthetic_failure(type_, "invalid_response_json", self._port)

        return _synthetic_failure(type_, "exhausted retries", self._port)

    def list_pending(self) -> dict[str, Any]:
        try:
            r = httpx.get(
                f"{self._base}/pending",
                headers=self._headers(),
                timeout=5.0,
            )
            return r.json()
        except Exception as exc:  # noqa: BLE001
            return {"error": f"{type(exc).__name__}: {exc}", "pending": []}

    def diagnostics(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "ui_port": self._port,
            "ui_base_url": self._base,
            "token_present": bool(self._token),
        }
        try:
            r = httpx.get(f"{self._base}/health", headers=self._headers(), timeout=2.0)
            out["health_status_code"] = r.status_code
            try:
                out["health"] = r.json()
            except Exception:  # noqa: BLE001
                out["health"] = {"raw": r.text[:200]}
        except Exception as exc:  # noqa: BLE001
            out["health_error"] = f"{type(exc).__name__}: {exc}"
        return out
