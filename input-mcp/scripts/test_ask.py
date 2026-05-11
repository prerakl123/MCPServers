"""Manual tester for the input-mcp UI service.

Reads token+port from ~/.mcp/input/, sends a single /ask request, prints the
JSON response. Designed to be run from a second terminal while ui_app (or
input-mcp's main.py) is running.

Usage examples:

    uv run python scripts/test_ask.py health
    uv run python scripts/test_ask.py pending

    uv run python scripts/test_ask.py text "What is your name?"
    uv run python scripts/test_ask.py text "Bio" --multiline --default "I love..."
    uv run python scripts/test_ask.py choice "Pick a color" red green blue
    uv run python scripts/test_ask.py choice "Pick toppings" cheese basil olives --multi
    uv run python scripts/test_ask.py confirm "Delete this file?"
    uv run python scripts/test_ask.py file "Pick a Python file" --filter "Python:*.py"
    uv run python scripts/test_ask.py file "Pick a folder" --mode directory
    uv run python scripts/test_ask.py form

    uv run python scripts/test_ask.py shutdown
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path.home() / ".mcp" / "input"


def _read_disco() -> tuple[int, str]:
    try:
        port = int((ROOT / "port").read_text(encoding="utf-8").strip())
        token = (ROOT / "token").read_text(encoding="utf-8").strip()
        return port, token
    except Exception as exc:
        sys.exit(
            f"could not read {ROOT}/port or /token: {exc}\n"
            "is ui_app running? start it first (see README)."
        )


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def cmd_health(args, port: int, token: str) -> None:
    r = httpx.get(f"http://127.0.0.1:{port}/health", headers=_headers(token), timeout=5)
    _print({"status_code": r.status_code, **r.json()})


def cmd_pending(args, port: int, token: str) -> None:
    r = httpx.get(f"http://127.0.0.1:{port}/pending", headers=_headers(token), timeout=5)
    _print(r.json())


def cmd_shutdown(args, port: int, token: str) -> None:
    r = httpx.post(f"http://127.0.0.1:{port}/shutdown", headers=_headers(token), timeout=5)
    _print({"status_code": r.status_code, **r.json()})


def _ask(port: int, token: str, body: dict) -> None:
    timeout = float(body.get("timeout_sec", 300)) + 30
    print(f"-- POST /ask  type={body['type']}  timeout={body['timeout_sec']}s --", flush=True)
    print("-- waiting for the popup; respond there. Ctrl+C aborts.", flush=True)
    r = httpx.post(
        f"http://127.0.0.1:{port}/ask",
        headers=_headers(token),
        json=body,
        timeout=timeout,
    )
    _print(r.json())


def cmd_text(args, port: int, token: str) -> None:
    body = {
        "type": "text",
        "prompt": args.prompt,
        "spec": {
            "default": args.default or "",
            "multiline": args.multiline,
            "placeholder": args.placeholder or "",
        },
        "timeout_sec": args.timeout,
        "origin": "test_ask",
    }
    _ask(port, token, body)


def cmd_choice(args, port: int, token: str) -> None:
    body = {
        "type": "choice",
        "prompt": args.prompt,
        "spec": {
            "options": args.options,
            "multi_select": args.multi,
            "allow_other": not args.no_other,
        },
        "timeout_sec": args.timeout,
        "origin": "test_ask",
    }
    _ask(port, token, body)


def cmd_confirm(args, port: int, token: str) -> None:
    body = {
        "type": "confirm",
        "prompt": args.prompt,
        "spec": {
            "confirm_label": args.yes,
            "deny_label": args.no,
            "default": args.default,
        },
        "timeout_sec": args.timeout,
        "origin": "test_ask",
    }
    _ask(port, token, body)


def cmd_file(args, port: int, token: str) -> None:
    filters = []
    for raw in args.filter or []:
        if ":" in raw:
            name, patterns = raw.split(":", 1)
            filters.append({"name": name, "patterns": patterns.split(",")})
    body = {
        "type": "file",
        "prompt": args.prompt,
        "spec": {
            "mode": args.mode,
            "filters": filters,
            "multiple": args.multiple,
        },
        "timeout_sec": args.timeout,
        "origin": "test_ask",
    }
    _ask(port, token, body)


def cmd_form(args, port: int, token: str) -> None:
    body = {
        "type": "form",
        "prompt": args.title,
        "spec": {
            "title": args.title,
            "fields": [
                {"name": "name", "label": "Your name", "type": "text", "required": True},
                {"name": "age", "label": "Age", "type": "number"},
                {"name": "bio", "label": "Bio", "type": "multiline",
                 "placeholder": "tell me about yourself"},
                {"name": "newsletter", "label": "Subscribe to newsletter",
                 "type": "checkbox", "checkbox_label": "yes please"},
                {"name": "color", "label": "Favorite color", "type": "choice",
                 "options": ["red", "green", "blue"]},
                {"name": "tags", "label": "Pick any tags", "type": "multi_choice",
                 "options": ["alpha", "beta", "gamma"]},
            ],
        },
        "timeout_sec": args.timeout,
        "origin": "test_ask",
    }
    _ask(port, token, body)


def main() -> None:
    parser = argparse.ArgumentParser(prog="test_ask")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("health")
    sub.add_parser("pending")
    sub.add_parser("shutdown")

    p = sub.add_parser("text")
    p.add_argument("prompt")
    p.add_argument("--default", default="")
    p.add_argument("--placeholder", default="")
    p.add_argument("--multiline", action="store_true")
    p.add_argument("--timeout", type=int, default=120)

    p = sub.add_parser("choice")
    p.add_argument("prompt")
    p.add_argument("options", nargs="+")
    p.add_argument("--multi", action="store_true")
    p.add_argument("--no-other", action="store_true")
    p.add_argument("--timeout", type=int, default=120)

    p = sub.add_parser("confirm")
    p.add_argument("prompt")
    p.add_argument("--yes", default="Yes")
    p.add_argument("--no", default="No")
    p.add_argument("--default", choices=["yes", "no"], default=None)
    p.add_argument("--timeout", type=int, default=120)

    p = sub.add_parser("file")
    p.add_argument("prompt")
    p.add_argument("--mode", choices=["open", "save", "directory"], default="open")
    p.add_argument("--filter", action="append",
                   help='Repeatable. Format: "Name:*.ext,*.ext2"')
    p.add_argument("--multiple", action="store_true")
    p.add_argument("--timeout", type=int, default=120)

    p = sub.add_parser("form")
    p.add_argument("--title", default="Sample form")
    p.add_argument("--timeout", type=int, default=300)

    args = parser.parse_args()
    port, token = _read_disco()

    handlers = {
        "health": cmd_health, "pending": cmd_pending, "shutdown": cmd_shutdown,
        "text": cmd_text, "choice": cmd_choice, "confirm": cmd_confirm,
        "file": cmd_file, "form": cmd_form,
    }
    handlers[args.cmd](args, port, token)


if __name__ == "__main__":
    main()
