from __future__ import annotations

import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class UsdzCommandResult:
    tool: str
    command: list[str]
    cwd: str | None
    returncode: int
    stdout: str
    stderr: str

    def to_dict(self) -> dict:
        return asdict(self)


def package_usdz(usda_path: Path, usdz_path: Path) -> UsdzCommandResult:
    usdzip = require_tool("usdzip")
    usda_path = usda_path.resolve()
    usdz_path = usdz_path.resolve()
    usdz_path.parent.mkdir(parents=True, exist_ok=True)
    command = [usdzip, str(usdz_path), usda_path.name]
    result = run_command(command, cwd=usda_path.parent)
    if result.returncode != 0:
        raise RuntimeError(command_failed_message("usdzip failed", result))
    remove_empty_usdzip_save_dir(usdz_path.parent)
    return result


def validate_usdz_arkit(usdz_path: Path) -> UsdzCommandResult:
    usdchecker = require_tool("usdchecker")
    command = [usdchecker, "--arkit", str(usdz_path)]
    result = run_command(command)
    if result.returncode != 0:
        raise RuntimeError(command_failed_message("usdchecker --arkit failed", result))
    return result


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise FileNotFoundError(f"Required USD tool not found on PATH: {name}")
    return path


def run_command(command: list[str], cwd: Path | None = None) -> UsdzCommandResult:
    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
    )
    return UsdzCommandResult(
        tool=Path(command[0]).name,
        command=command,
        cwd=str(cwd) if cwd else None,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def remove_empty_usdzip_save_dir(parent: Path) -> None:
    save_dir = parent / "(A Document Being Saved By usdzip)"
    try:
        save_dir.rmdir()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def command_failed_message(prefix: str, result: UsdzCommandResult) -> str:
    details = (result.stderr or result.stdout).strip()
    if details:
        return f"{prefix}: {details}"
    return f"{prefix}: exit code {result.returncode}"
