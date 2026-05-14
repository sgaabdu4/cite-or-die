from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any
from urllib.request import urlopen

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


def normalize_record(record: dict[str, Any], source: str) -> dict[str, Any]:
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


def sample_records(limit: int, seed: int) -> tuple[int, list[dict[str, Any]]]:
    rng = random.Random(seed)  # noqa: S311 - deterministic eval sampling, not security.
    sample: list[dict[str, Any]] = []
    seen = 0
    for source, url in DATASET_SOURCES:
        with urlopen(url, timeout=60) as response:  # noqa: S310 - fixed HTTPS dataset URLs.
            for raw_line in response:
                line = raw_line.strip()
                if not line:
                    continue
                seen += 1
                record = normalize_record(json.loads(line), source)
                if len(sample) < limit:
                    sample.append(record)
                    continue
                index = rng.randrange(seen)
                if index < limit:
                    sample[index] = record
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
