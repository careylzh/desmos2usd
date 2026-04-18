from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .desmos_url import parse_desmos_url


class FetchError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def fetch_url_json(url: str, timeout: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "desmos2usd/0.1 (+https://www.desmos.com)",
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise FetchError(f"Unable to fetch {url}: {exc}") from exc

    content = raw.lstrip()
    if content.startswith("{"):
        return json.loads(raw)
    state = extract_state_from_html(raw)
    if state is None:
        raise FetchError(f"Fetched {url}, but no Desmos state JSON was found")
    return state


def extract_state_from_html(html: str) -> dict[str, Any] | None:
    patterns = [
        r"window\.__(?:DESMOS_)?INITIAL_STATE__\s*=\s*({.*?})\s*;",
        r"Calc\.setState\((\{.*?\})\);",
        r'"state"\s*:\s*(\{.*?\})\s*,\s*"thumbUrl"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)
        if not match:
            continue
        candidate = match.group(1)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def fetch_graph_state(url: str, project_root: Path, refresh: bool = False) -> dict[str, Any]:
    parsed = parse_desmos_url(url)
    fixture_path = project_root / "fixtures" / "states" / f"{parsed.graph_hash}.json"
    if fixture_path.exists() and not refresh:
        # Record the fixture path as a project-relative reference so the committed
        # USDA does not expose the absolute local path (e.g., "/Users/chek/...").
        try:
            state_url = fixture_path.relative_to(project_root).as_posix()
        except ValueError:
            state_url = fixture_path.name
        return normalize_fetched_payload(load_json(fixture_path), parsed.url, parsed.graph_hash, state_url)

    endpoints = [
        f"https://www.desmos.com/calculator_backend/graphs/{parsed.graph_hash}",
        f"https://www.desmos.com/calculator_backend/graphs/3d/{parsed.graph_hash}",
        parsed.url,
    ]
    errors: list[str] = []
    for endpoint in endpoints:
        try:
            payload = fetch_url_json(endpoint)
            return normalize_fetched_payload(payload, parsed.url, parsed.graph_hash, endpoint)
        except FetchError as exc:
            errors.append(str(exc))
        except json.JSONDecodeError as exc:
            errors.append(f"{endpoint}: invalid JSON: {exc}")
    joined = "\n".join(f"- {error}" for error in errors)
    raise FetchError(f"Could not fetch Desmos state for {parsed.url}\n{joined}")


def normalize_fetched_payload(payload: dict[str, Any], url: str, graph_hash: str, endpoint: str) -> dict[str, Any]:
    if "state" in payload and isinstance(payload["state"], dict):
        state = payload["state"]
        title = str(payload.get("title") or state.get("title") or graph_hash)
    else:
        state = payload
        title = str(payload.get("title") or graph_hash)
    state.setdefault("version", 1)
    state.setdefault("graph", {})
    state["graph"].setdefault("hash", graph_hash)
    state["graph"].setdefault("url", url)
    state["graph"].setdefault("state_url", endpoint)
    state["graph"].setdefault("title", title)
    if "expressions" not in state:
        raise FetchError(f"Fetched state for {url} has no expressions list")
    return state
