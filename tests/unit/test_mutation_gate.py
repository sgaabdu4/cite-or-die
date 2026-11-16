from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import mutation_gate

FOUR_TESTS = [
    "tests/unit/test_input_guard.py",
    "tests/unit/test_citation_verifier.py",
    "tests/integration/test_phase2_walls.py",
    "tests/integration/test_service.py",
]


def test_each_mutation_runs_the_same_four_tests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target.py"
    target.write_text("value = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        mutation_gate,
        "MUTATIONS",
        [mutation_gate.Mutation("flip", target, "value = 1", "value = 2")],
    )
    run = Mock(return_value=subprocess.CompletedProcess([], 1))
    monkeypatch.setattr(mutation_gate.subprocess, "run", run)

    score, results = mutation_gate.run_mutation_gate(0.5)

    assert run.call_args.args[0] == [sys.executable, "-m", "pytest", *FOUR_TESTS]
    assert score == 1.0
    assert [result.killed for result in results] == [True]
    assert target.read_text(encoding="utf-8") == "value = 1\n"
