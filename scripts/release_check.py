from __future__ import annotations

import re
import shutil
import subprocess
import tomllib
from pathlib import Path

EXPECTED_VERSION = "1.1.0"


def main() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    package_version = pyproject["project"]["version"]
    init_text = Path("src/cite_or_die/__init__.py").read_text(encoding="utf-8")
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    init_version = _match(r'__version__ = "([^"]+)"', init_text, "package __version__")
    compose_version = _match(
        r"image: cite-or-die:([0-9]+\.[0-9]+\.[0-9]+)",
        compose_text,
        "image tag",
    )
    versions = {
        "pyproject": package_version,
        "__init__": init_version,
        "compose_image": compose_version,
    }
    mismatches = {
        name: version for name, version in versions.items() if version != EXPECTED_VERSION
    }
    if mismatches:
        raise SystemExit(f"release version mismatch: {mismatches}")
    tracked_node_modules = _tracked_node_modules()
    if tracked_node_modules:
        sample = ", ".join(tracked_node_modules[:5])
        raise SystemExit(f"tracked node_modules entries are not allowed: {sample}")
    print(f"release-check ok: cite-or-die {EXPECTED_VERSION}")


def _match(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text)
    if match is None:
        raise SystemExit(f"missing {label}")
    return match.group(1)


def _tracked_node_modules() -> list[str]:
    git = shutil.which("git")
    if git is None:
        raise SystemExit("missing git executable")
    result = subprocess.run(  # noqa: S603 - git path is resolved and arguments are fixed.
        [git, "ls-files", "*node_modules*"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [path for path in result.stdout.splitlines() if "node_modules" in Path(path).parts]


if __name__ == "__main__":
    main()
