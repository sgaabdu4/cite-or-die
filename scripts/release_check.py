from __future__ import annotations

import re
import tomllib
from pathlib import Path

EXPECTED_VERSION = "1.0.0"


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
    print(f"release-check ok: cite-or-die {EXPECTED_VERSION}")


def _match(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text)
    if match is None:
        raise SystemExit(f"missing {label}")
    return match.group(1)


if __name__ == "__main__":
    main()
