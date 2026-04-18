from __future__ import annotations

from pathlib import Path
from typing import Any

from .desmos_fetch import fetch_graph_state, load_json
from .desmos_url import parse_desmos_url


REQUIRED_SAMPLE_URLS = [
    "https://www.desmos.com/3d/zaqxhna15w",
    "https://www.desmos.com/3d/ghnr7txz47",
    "https://www.desmos.com/3d/yuqwjsfvsc",
    "https://www.desmos.com/3d/vyp9ogyimt",
    "https://www.desmos.com/3d/k0fbxxwkqf",
]


def project_root_from_cwd() -> Path:
    current = Path.cwd()
    for candidate in [current, *current.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "fixtures").is_dir():
            return candidate
    return current


def load_state_for_url(url: str, project_root: Path | None = None, refresh: bool = False) -> dict[str, Any]:
    root = project_root or project_root_from_cwd()
    return fetch_graph_state(url, root, refresh=refresh)


def load_fixture_state(url: str, project_root: Path | None = None) -> dict[str, Any]:
    root = project_root or project_root_from_cwd()
    parsed = parse_desmos_url(url)
    return load_json(root / "fixtures" / "states" / f"{parsed.graph_hash}.json")

