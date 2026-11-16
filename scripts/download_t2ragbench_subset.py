from __future__ import annotations

import argparse
import hashlib
import heapq
import json
from collections.abc import Iterable, Iterator
from pathlib import Path

import httpx

DATASET_SOURCES = (
    (
        "ConvFinQA",
        "https://huggingface.co/datasets/G4KMU/t2-ragbench/resolve/main/data/ConvFinQA/turn_0.jsonl",
    ),
    (
        "FinQA-test",
        "https://huggingface.co/datasets/G4KMU/t2-ragbench/resolve/main/data/FinQA/test/metadata.jsonl",
    ),
    (
        "FinQA-dev",
        "https://huggingface.co/datasets/G4KMU/t2-ragbench/resolve/main/data/FinQA/dev/metadata.jsonl",
    ),
    (
        "FinQA-train",
        "https://huggingface.co/datasets/G4KMU/t2-ragbench/resolve/main/data/FinQA/train/metadata.jsonl",
    ),
    (
        "TAT-DQA-test",
        "https://huggingface.co/datasets/G4KMU/t2-ragbench/resolve/main/data/TAT-DQA/test/metadata.jsonl",
    ),
    (
        "TAT-DQA-dev",
        "https://huggingface.co/datasets/G4KMU/t2-ragbench/resolve/main/data/TAT-DQA/dev/metadata.jsonl",
    ),
    (
        "TAT-DQA-train",
        "https://huggingface.co/datasets/G4KMU/t2-ragbench/resolve/main/data/TAT-DQA/train/metadata.jsonl",
    ),
)


def normalize_record(record: dict[str, object], source: str) -> dict[str, str]:
    return {
        "id": str(record["id"]),
        "context_id": str(record["context_id"]),
        "source": source,
        "split": str(record.get("split", "")),
        "question": str(record["question"]),
        "program_answer": str(record.get("program_answer", "")),
        "original_answer": str(record.get("original_answer", "")),
        "context": str(record["context"]),
        "file_name": str(record.get("file_name", "")),
    }


def json_lines(url: str) -> Iterator[bytes]:
    with httpx.stream("GET", url, timeout=60, follow_redirects=True) as response:
        response.raise_for_status()
        pending = b""
        for chunk in response.iter_bytes():
            *lines, pending = (pending + chunk).split(b"\n")
            yield from lines
        if pending:
            yield pending


def pick_sample(records: Iterable[dict[str, str]], limit: int, seed: int) -> list[dict[str, str]]:
    def order(record: dict[str, str]) -> str:
        return hashlib.sha256(f"{seed}:{record['id']}".encode()).hexdigest()

    return heapq.nsmallest(limit, records, key=order)


def sample_records(limit: int, seed: int) -> tuple[int, list[dict[str, str]]]:
    seen = 0

    def rows() -> Iterator[dict[str, str]]:
        nonlocal seen
        for source, url in DATASET_SOURCES:
            for raw_line in json_lines(url):
                line = raw_line.strip()
                if not line:
                    continue
                seen += 1
                yield normalize_record(json.loads(line), source)

    sample = pick_sample(rows(), limit, seed)
    return seen, sample


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download a deterministic T2-RAGBench JSONL subset."
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260514)
    parser.add_argument("--output", type=Path, default=Path("examples/t2ragbench_subset.jsonl"))
    args = parser.parse_args()

    seen, records = sample_records(args.limit, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"wrote {len(records)} of {seen} rows to {args.output}")


if __name__ == "__main__":
    main()
