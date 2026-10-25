import sys
from types import ModuleType

import pytest

from cite_or_die.security import input_guard


@pytest.mark.parametrize(
    ("label", "score", "topic_scores", "expected_prompt", "expected_topics"),
    [
        ("INJECTION", 0.9, [0.8, 0.1, 0.1], (False, 0.8), (False, 0.6)),
        ("SAFE", 0.8, [0.3, 0.3, 0.4], (True, -0.6), (True, -0.2)),
        ("INJECTION", 0.5, [0.5, 0.3, 0.2], (True, 0.0), (True, 0.0)),
    ],
)
def test_model_guard_preserves_models_thresholds_and_scores(
    monkeypatch: pytest.MonkeyPatch,
    label: str,
    score: float,
    topic_scores: list[float],
    expected_prompt: tuple[bool, float],
    expected_topics: tuple[bool, float],
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class Pipeline:
        def __init__(self, task: str) -> None:
            self.task = task

        def __call__(self, text: str, **options: object) -> object:
            assert text == "ordinary content"
            assert options["max_length"] == 512
            assert options["truncation"] is True
            if self.task == "text-classification":
                return [{"label": label, "score": score}]
            assert options["candidate_labels"] == input_guard.BANNED_TOPICS
            assert options["multi_label"] is False
            return {"scores": topic_scores}

    def pipeline(task: str, **options: object) -> Pipeline:
        calls.append((task, options))
        return Pipeline(task)

    module = ModuleType("transformers")
    monkeypatch.setattr(module, "pipeline", pipeline, raising=False)
    monkeypatch.setitem(sys.modules, "transformers", module)
    scanner = input_guard.LlmGuardScanner()

    assert scanner.scan_prompt_injection("ordinary content") == expected_prompt
    assert scanner.scan_ban_topics("ordinary content") == expected_topics
    assert scanner.scan_prompt_injection(" ") == (True, -1.0)
    assert scanner.scan_ban_topics(" ") == (True, -1.0)
    assert calls == [
        (
            "text-classification",
            {
                "model": "protectai/deberta-v3-base-prompt-injection-v2",
                "revision": "89b085cd330414d3e7d9dd787870f315957e1e9f",
            },
        ),
        (
            "zero-shot-classification",
            {
                "model": "MoritzLaurer/roberta-base-zeroshot-v2.0-c",
                "revision": "d825e740e0c59881cf0b0b1481ccf726b6d65341",
            },
        ),
    ]


def test_enabled_model_guard_does_not_silently_fall_back(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable() -> input_guard.GuardScanner:
        raise RuntimeError("model is unavailable")

    monkeypatch.setenv("CITE_OR_DIE_ENABLE_LLM_GUARD_MODELS", "1")
    monkeypatch.setattr(input_guard, "LlmGuardScanner", unavailable)
    input_guard._llm_guard_scanner.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="model is unavailable"):
            input_guard.scan_user_text("ordinary content")
    finally:
        input_guard._llm_guard_scanner.cache_clear()
