from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class DesmosUrl:
    url: str
    graph_hash: str
    calculator: str = "3d"


def parse_desmos_url(url: str) -> DesmosUrl:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Desmos URL must use http or https: {url}")
    if parsed.netloc not in {"www.desmos.com", "desmos.com"}:
        raise ValueError(f"Expected desmos.com URL, got: {url}")
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"Expected Desmos share URL with a graph hash: {url}")
    calculator, graph_hash = parts[0], parts[1]
    if calculator != "3d":
        raise ValueError(f"Only Desmos 3D URLs are supported, got /{calculator}/")
    if not graph_hash.replace("-", "").isalnum():
        raise ValueError(f"Invalid Desmos graph hash: {graph_hash}")
    return DesmosUrl(url=f"https://www.desmos.com/3d/{graph_hash}", graph_hash=graph_hash)


def fixture_state_path(root: str, graph_hash: str) -> str:
    return f"{root}/fixtures/states/{graph_hash}.json"

