from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Mutation:
    name: str
    path: Path
    original: str
    replacement: str


@dataclass(frozen=True)
class MutationResult:
    name: str
    killed: bool


MUTATIONS = [
    Mutation(
        name="input_guard_uses_and_for_regex",
        path=Path("src/cite_or_die/security/input_guard.py"),
        original="if regex_rejected or not llm_guard_valid:",
        replacement="if regex_rejected and not llm_guard_valid:",
    ),
    Mutation(
        name="retrieved_guard_uses_and_for_regex",
        path=Path("src/cite_or_die/security/input_guard.py"),
        original="if regex_rejected or not topic_valid:",
        replacement="if regex_rejected and not topic_valid:",
    ),
    Mutation(
        name="normalization_keeps_zero_width",
        path=Path("src/cite_or_die/security/input_guard.py"),
        original='normalized = unicodedata.normalize("NFKC", ZERO_WIDTH.sub("", text))',
        replacement='normalized = unicodedata.normalize("NFKC", text)',
    ),
    Mutation(
        name="wall_scope_accepts_wrong_tenant",
        path=Path("src/cite_or_die/security/walls.py"),
        original="if citation.tenant_id != tenant_id or citation.matter_id != matter_id:",
        replacement="if citation.tenant_id == tenant_id or citation.matter_id == matter_id:",
    ),
    Mutation(
        name="citation_verifier_inverts_substring_check",
        path=Path("src/cite_or_die/security/citation_verifier.py"),
        original="if normalize_for_match(citation.quote) in normalize_for_match(chunk.text):",
        replacement=(
            "if normalize_for_match(citation.quote) not in normalize_for_match(chunk.text):"
        ),
    ),
]

TARGETED_TESTS = [
    "tests/unit/test_input_guard.py",
    "tests/unit/test_citation_verifier.py",
    "tests/integration/test_phase2_walls.py",
    "tests/integration/test_service.py",
]


def run_mutation_gate(threshold: float) -> tuple[float, list[MutationResult]]:
    backups = {mutation.path: mutation.path.read_text(encoding="utf-8") for mutation in MUTATIONS}
    results: list[MutationResult] = []
    try:
        for mutation in MUTATIONS:
            source = backups[mutation.path]
            if mutation.original not in source:
                results.append(MutationResult(name=mutation.name, killed=False))
                continue
            mutation.path.write_text(
                source.replace(mutation.original, mutation.replacement, 1),
                encoding="utf-8",
            )
            command = [sys.executable, "-m", "pytest", *TARGETED_TESTS]
            completed = subprocess.run(command, check=False, capture_output=True, text=True)  # noqa: S603
            results.append(MutationResult(name=mutation.name, killed=completed.returncode != 0))
            mutation.path.write_text(source, encoding="utf-8")
    finally:
        for path, content in backups.items():
            path.write_text(content, encoding="utf-8")

    score = sum(result.killed for result in results) / len(results)
    if score < threshold:
        return score, results
    return score, results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.70)
    args = parser.parse_args()

    score, results = run_mutation_gate(args.threshold)
    print(
        json.dumps(
            {
                "kill_rate": score,
                "threshold": args.threshold,
                "results": [asdict(result) for result in results],
            },
            indent=2,
        )
    )
    if score < args.threshold:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
