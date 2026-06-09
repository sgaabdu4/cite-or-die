import re
from collections.abc import Iterable

from cite_or_die.core.models import Citation, Claim, DocumentChunk, LLMAnswer

SPACE = re.compile(r"\s+")
WORD = re.compile(r"[a-z0-9]+")
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
WHAT_IS_QUERY = re.compile(
    r"\bwhat\s+(?:is|are)\s+(?P<object>[a-z0-9][a-z0-9 +#./-]{1,80}?)(?=[?.,;:]|$)"
)
DEFINE_QUERY = re.compile(
    r"\b(?:define|definition\s+of|meaning\s+of)\s+"
    r"(?P<object>[a-z0-9][a-z0-9 +#./-]{1,80}?)(?=[?.,;:]|$)"
)
QUERY_STOPWORDS = {
    "a",
    "an",
    "are",
    "is",
    "of",
    "the",
    "what",
}
DEFINITION_NOUNS = {
    "approach",
    "architecture",
    "framework",
    "method",
    "model",
    "process",
    "system",
    "technique",
}
DEFINITION_VERBS = {
    "combines",
    "connects",
    "links",
    "retrieves",
    "uses",
}


def build_extractive_definition_answer(
    question: str, chunks: Iterable[DocumentChunk]
) -> LLMAnswer | None:
    target_terms = _definition_target_terms(question)
    if not target_terms:
        return None

    candidates: list[tuple[float, int, int, DocumentChunk, str]] = []
    for chunk_index, chunk in enumerate(chunks):
        for sentence_index, sentence in enumerate(_sentences(chunk.text)):
            score = _definition_support_score(sentence, target_terms)
            if score > 0:
                candidates.append((score, -chunk_index, -sentence_index, chunk, sentence))
    if not candidates:
        return None

    _, _, _, chunk, quote = max(candidates, key=lambda item: item[:3])
    citation = Citation(
        chunk_id=chunk.chunk_id,
        doc_id=chunk.doc_id,
        filename=chunk.filename,
        tenant_id=chunk.tenant_id,
        matter_id=chunk.matter_id,
        page=chunk.page,
        quote=quote,
    )
    return LLMAnswer(
        answer=quote,
        claims=[
            Claim(
                text=quote,
                citations=[citation],
            )
        ],
    )


def has_definition_support(question: str, answer: LLMAnswer) -> bool:
    target_terms = _definition_target_terms(question)
    if not target_terms:
        return True
    return any(
        _definition_support_score(citation.quote, target_terms) > 0
        for claim in answer.claims
        for citation in claim.citations
    )


def _definition_target_terms(question: str) -> set[str]:
    normalized = _normalize(question)
    for pattern in (WHAT_IS_QUERY, DEFINE_QUERY):
        match = pattern.search(normalized)
        if match:
            return _content_terms(match.group("object"))
    return set()


def _sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in SENTENCE_BOUNDARY.split(text)
        if sentence.strip() and sentence.strip()[-1] in ".!?"
    ]


def _definition_support_score(text: str, target_terms: set[str]) -> float:
    normalized = _normalize(text)
    terms = _content_terms(normalized)
    if not target_terms.intersection(terms):
        return 0.0

    score = 0.0
    target_pattern = _target_pattern(target_terms)
    if re.search(rf"\b[a-z][a-z -]{{3,}}\s+\({target_pattern}\)", normalized):
        score += 1.5
    if re.search(
        rf"{target_pattern}\s+(?:is|are|was|were|means|refers\s+to|is\s+defined\s+as)\b",
        normalized,
    ):
        score += 1.5
    if re.search(rf"{target_pattern}\b[^.!?]{{0,100}}\bas\s+(?:a|an|the)\b", normalized):
        score += 1.25
    if re.search(rf"\bintroduced\s+{target_pattern}\s+as\s+(?:a|an|the)\b", normalized):
        score += 1.0
    if terms.intersection(DEFINITION_NOUNS):
        score += 0.5
    if terms.intersection(DEFINITION_VERBS):
        score += 1.0
    return score


def _target_pattern(target_terms: set[str]) -> str:
    alternatives = sorted((re.escape(term) for term in target_terms), key=len, reverse=True)
    return rf"\b(?:{'|'.join(alternatives)})\b"


def _content_terms(text: str) -> set[str]:
    return {
        word
        for word in WORD.findall(_normalize(text))
        if len(word) > 1 and word not in QUERY_STOPWORDS
    }


def _normalize(text: str) -> str:
    return SPACE.sub(" ", text).strip().casefold()
