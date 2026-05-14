from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class CorpusItem:
    filename: str
    url: str
    license: str


CORPUS = [
    CorpusItem(
        "tesla_10k.html",
        "https://www.sec.gov/Archives/edgar/data/1318605/000162828025003063/tsla-20241231.htm",
        "Public domain (SEC EDGAR)",
    ),
    CorpusItem(
        "uber_10k.html",
        "https://www.sec.gov/Archives/edgar/data/1543151/000154315125000008/uber-20241231.htm",
        "Public domain (SEC EDGAR)",
    ),
    CorpusItem(
        "snowflake_10k.pdf",
        "https://s26.q4cdn.com/463892824/files/doc_financials/2024/q4/Snowflake-FY24-10K.pdf",
        "Public investor-relations filing",
    ),
]


def download(item: CorpusItem, examples_dir: Path) -> Path:
    path = examples_dir / item.filename
    if path.exists() and path.stat().st_size > 0:
        return path

    request = Request(  # noqa: S310 - fixed public corpus URLs.
        item.url,
        headers={
            "User-Agent": "cite-or-die dev corpus downloader contact@example.com",
        },
    )
    with urlopen(request, timeout=60) as response:  # noqa: S310 - fixed public corpus URLs.
        path.write_bytes(response.read())
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(items: list[CorpusItem], examples_dir: Path) -> None:
    rows = [
        "# Examples Manifest",
        "",
        "| File | SHA-256 | License | Source |",
        "|---|---|---|---|",
    ]
    for item in items:
        path = examples_dir / item.filename
        rows.append(f"| `{item.filename}` | `{sha256(path)}` | {item.license} | {item.url} |")
    rows.append("")
    (examples_dir / "MANIFEST.md").write_text("\n".join(rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--examples-dir", default="examples")
    parser.add_argument("--tesla-only", action="store_true")
    args = parser.parse_args()

    examples_dir = Path(args.examples_dir)
    examples_dir.mkdir(parents=True, exist_ok=True)
    items = CORPUS[:1] if args.tesla_only else CORPUS
    for item in items:
        download(item, examples_dir)
    write_manifest(items, examples_dir)


if __name__ == "__main__":
    main()
