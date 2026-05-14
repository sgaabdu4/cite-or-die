from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any, cast

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpArtifacts, NlpEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig


@dataclass(frozen=True)
class PiiRedaction:
    text: str
    count: int
    entities: list[PiiEntity]


@dataclass(frozen=True)
class PiiEntity:
    entity_type: str
    start: int
    end: int
    replacement: str
    page: int | None = None


class NoOpNlpEngine(NlpEngine):
    """NLP stub for Presidio pattern recognizers that do not need token features."""

    def load(self) -> None:
        return None

    def is_loaded(self) -> bool:
        return True

    def process_text(self, text: str, language: str) -> NlpArtifacts:
        return NlpArtifacts([], cast(Any, []), [], [], self, language)

    def process_batch(
        self,
        texts: Iterable[str],
        language: str,
        batch_size: int = 1,
        n_process: int = 1,
        **kwargs: object,
    ) -> Iterator[tuple[str, NlpArtifacts]]:
        for text in texts:
            yield text, self.process_text(text, language)

    def is_stopword(self, word: str, language: str) -> bool:
        return False

    def is_punct(self, word: str, language: str) -> bool:
        return False

    def get_supported_entities(self) -> list[str]:
        return []

    def get_supported_languages(self) -> list[str]:
        return ["en"]


def _build_analyzer() -> AnalyzerEngine:
    registry = RecognizerRegistry(supported_languages=["en"])
    registry.add_recognizer(
        PatternRecognizer(
            supported_entity="EMAIL_ADDRESS",
            patterns=[
                Pattern(
                    name="email",
                    regex=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
                    score=0.95,
                )
            ],
        )
    )
    registry.add_recognizer(
        PatternRecognizer(
            supported_entity="US_SSN",
            patterns=[Pattern(name="ssn", regex=r"\b\d{3}-\d{2}-\d{4}\b", score=0.95)],
        )
    )
    registry.add_recognizer(
        PatternRecognizer(
            supported_entity="PHONE_NUMBER",
            patterns=[
                Pattern(
                    name="phone",
                    regex=r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b",
                    score=0.85,
                )
            ],
        )
    )
    # Source: https://github.com/microsoft/presidio is the brief's local PII redaction layer.
    return AnalyzerEngine(
        registry=registry,
        nlp_engine=NoOpNlpEngine(),
        supported_languages=["en"],
    )


ANALYZER = _build_analyzer()
ANONYMIZER = AnonymizerEngine()
REPLACEMENTS = {
    "EMAIL_ADDRESS": "<EMAIL>",
    "US_SSN": "<SSN>",
    "PHONE_NUMBER": "<PHONE>",
}
OPERATORS = {
    entity_type: OperatorConfig("replace", {"new_value": replacement})
    for entity_type, replacement in REPLACEMENTS.items()
}


def redact_pii(text: str) -> PiiRedaction:
    results = ANALYZER.analyze(text=text, language="en")
    anonymized = ANONYMIZER.anonymize(
        text=text,
        analyzer_results=cast(Any, results),
        operators=OPERATORS,
    )
    entities = [
        PiiEntity(
            entity_type=result.entity_type,
            start=result.start,
            end=result.end,
            replacement=REPLACEMENTS[result.entity_type],
        )
        for result in results
        if result.entity_type in OPERATORS
    ]
    return PiiRedaction(text=anonymized.text, count=len(entities), entities=entities)


def redact_pii_pages(
    pages: list[tuple[str, int | None]],
) -> tuple[list[tuple[str, int | None]], int, list[PiiEntity]]:
    total = 0
    redacted_pages: list[tuple[str, int | None]] = []
    entities: list[PiiEntity] = []
    for text, page in pages:
        redaction = redact_pii(text)
        total += redaction.count
        entities.extend(
            PiiEntity(
                entity_type=entity.entity_type,
                start=entity.start,
                end=entity.end,
                replacement=entity.replacement,
                page=page,
            )
            for entity in redaction.entities
        )
        redacted_pages.append((redaction.text, page))
    return redacted_pages, total, entities
