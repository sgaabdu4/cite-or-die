import csv
import json
import math
from pathlib import Path
from typing import TypedDict, cast


class BenchmarkStats(TypedDict):
    mean: float


class BenchmarkResult(TypedDict):
    name: str
    stats: BenchmarkStats


class BenchmarkReport(TypedDict):
    benchmarks: list[BenchmarkResult]


ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "coverage" / "performance"


def _benchmark_mean(output: Path) -> float:
    report = cast(BenchmarkReport, json.loads(output.read_text()))
    assert len(report["benchmarks"]) == 1
    mean = report["benchmarks"][0]["stats"]["mean"]
    assert mean > 0
    return mean


def test_retrieval_mean_does_not_regress_ten_percent_from_main() -> None:
    main_mean = _benchmark_mean(REPORTS / "main.json")
    current_mean = _benchmark_mean(REPORTS / "current.json")
    print(f"Retrieval mean: main={main_mean:.6f}s current={current_mean:.6f}s")
    assert current_mean <= main_mean * 1.10


def test_ten_users_meet_retrieval_and_chat_p95_budgets() -> None:
    with (REPORTS / "load_stats.csv").open() as handle:
        chat = next(row for row in csv.DictReader(handle) if row["Name"] == "/chat")
    retrieval_ms = cast(list[float], json.loads((REPORTS / "retrieval-ms.json").read_text()))
    assert int(chat["Request Count"]) >= 100
    assert int(chat["Failure Count"]) == 0
    assert len(retrieval_ms) >= 100
    retrieval_p95 = sorted(retrieval_ms)[math.ceil(len(retrieval_ms) * 0.95) - 1]
    print(f"Retrieval P95={retrieval_p95:.2f}ms; chat P95={chat['95%']}ms")
    assert retrieval_p95 < 500
    assert float(chat["95%"]) < 2000
