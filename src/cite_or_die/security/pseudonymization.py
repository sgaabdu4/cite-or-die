from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from cite_or_die.core.config import Settings
from cite_or_die.core.models import DocumentChunk
from cite_or_die.security.pii import PiiEntity

_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_KDF_INFO_PREFIX = b"cod-pseudonym-map:"
_NONCE_BYTES = 12
_KEY_BYTES = 32
_COMPANY_PATTERN = re.compile(
    r"\b(?P<name>[A-Z][A-Za-z0-9&'.-]*(?:\s+[A-Z][A-Za-z0-9&'.-]*){0,5}\s+"
    r"(?:Ltd|Limited|PLC|plc|LLC|Inc|Corp|Corporation|Company|Group))\b"
)
_CUSTOMER_WORD = (
    r"(?:[A-Z](?:\.[A-Z])+\.?|[A-Z][A-Za-z0-9&'-]+|"
    r"\d[A-Za-z0-9&'.-]*[A-Z][A-Za-z0-9&'.-]*)"
)
_CUSTOMER_LEADING_STOPWORDS = (
    r"(?:Did|Does|Do|Will|Can|Could|Should|Would|Has|Have|Had|Is|Are|Was|Were|"
    r"What|Which|Who|When|Where|Why|How)"
)
_CUSTOMER_QUESTION_AUXILIARY = r"(?:Did|Does|Do|Will|Can|Could|Should|Would|Has|Have|Had)"
_CUSTOMER_FIRST_WORD = (
    rf"(?!{_CUSTOMER_LEADING_STOPWORDS}\b){_CUSTOMER_WORD}"
)
_CUSTOMER_NAME = rf"{_CUSTOMER_FIRST_WORD}(?:\s+{_CUSTOMER_WORD}){{0,4}}"
_CUSTOMER_ACTION = (
    r"(?:generat(?:e|es|ed)|renew(?:s|ed)?|approv(?:e|es|ed)|sign(?:s|ed)?|"
    r"represent(?:s|ed)?|account(?:s|ed)?|contract(?:s|ed)?|contribut(?:e|es|ed)|"
    r"deliver(?:s|ed)?|provid(?:e|es|ed)|produc(?:e|es|ed))"
)
_CUSTOMER_RELATION = r"(?:from|with|for|to|by)"
_CUSTOMER_SEPARATOR = r"(?i:and|or|versus|vs\.?|v\.?)"
_CUSTOMER_CHAIN_SEPARATOR = rf"(?:\s+{_CUSTOMER_SEPARATOR}\s+|\s*,\s*(?:{_CUSTOMER_SEPARATOR}\s+)?)"
_CUSTOMER_CONTINUATION = (
    rf"(?:{_CUSTOMER_ACTION}|(?i:is|are|was|were|has|have|had|reported|"
    r"contributed|delivered|provided|produced|total(?:ed|led)?))"
)
_CUSTOMER_TEMPORAL = (
    r"(?i:(?:in|during|through|after|before)\s+"
    r"(?:FY\d{2,4}|Q[1-4]|H[12]|20\d{2}|19\d{2}))"
)
_CUSTOMER_TERMINATOR = (
    rf"(?=\s+{_CUSTOMER_CONTINUATION}\b"
    rf"|(?:\s+{_CUSTOMER_CONTINUATION})?[,.;:?!]"
    rf"|\s+{_CUSTOMER_RELATION}\s+"
    rf"|\s+{_CUSTOMER_SEPARATOR}\s+"
    rf"|\s+{_CUSTOMER_TEMPORAL}\b"
    r"|\s*$)"
)
_CUSTOMER_CONTEXT_PATTERN = re.compile(
    rf"\b{_CUSTOMER_RELATION}\s+(?P<name>{_CUSTOMER_NAME}){_CUSTOMER_TERMINATOR}"
)
_CUSTOMER_NOUN_PATTERN = re.compile(
    rf"\b(?:customer|client|account)\s+(?P<name>{_CUSTOMER_NAME}){_CUSTOMER_TERMINATOR}"
)
_CUSTOMER_CHAIN_PATTERN = re.compile(
    rf"{_CUSTOMER_CHAIN_SEPARATOR}(?P<name>{_CUSTOMER_NAME}){_CUSTOMER_TERMINATOR}"
)
_CUSTOMER_FORWARD_PATTERN = re.compile(
    rf"\b(?:{_CUSTOMER_QUESTION_AUXILIARY}\s+)?(?P<name>{_CUSTOMER_NAME})"
    rf"(?=(?:{_CUSTOMER_CHAIN_SEPARATOR}{_CUSTOMER_NAME})*\s+{_CUSTOMER_ACTION}\b)"
)
_PERSON_ACTION = (
    r"(?:approve[ds]?|sign(?:s|ed)?|authori[sz]e[ds]?|review(?:s|ed)?|"
    r"request(?:s|ed)?|respond(?:s|ed)?)"
)
_PERSON_NAME = (
    r"(?!(?:Did|Does|Do|Will|Can|Could|Should|Would|Is|Are|Was|Were)\s)"
    r"(?:[A-Z][a-z]+|[A-Z]\.?)(?:\s+(?:[A-Z][a-z]+|[A-Z]\.?)){1,3}"
)
_PERSON_FORWARD_PATTERN = re.compile(
    rf"\b(?P<name>{_PERSON_NAME})\s+"
    rf"{_PERSON_ACTION}\b"
)
_PERSON_BY_PATTERN = re.compile(
    rf"\b{_PERSON_ACTION}\s+by\s+"
    rf"(?P<name>{_PERSON_NAME})\b"
)
_GENERIC_FALSE_POSITIVES = {
    "Annual Report",
    "Board Meeting",
    "Change Control",
    "Customer Data",
    "Deal Room",
    "Financial Statements",
    "Human Resources",
    "Information Request",
    "Management Presentation",
    "Master Services",
    "Operational Report",
    "Public Market",
    "Risk Register",
    "Source Library",
}
_COMPANY_SUFFIXES = (
    " ltd",
    " limited",
    " plc",
    " llc",
    " inc",
    " corp",
    " corporation",
    " company",
    " group",
)
_PSEUDONYM_MAP_LOCKS: dict[tuple[str, str, str], threading.Lock] = {}
_PSEUDONYM_MAP_LOCKS_GUARD = threading.Lock()
_PSEUDONYM_MAP_UPDATE_ATTEMPTS = 3
_T = TypeVar("_T")


class InvalidPseudonymMapError(RuntimeError):
    pass


class PseudonymMapConflictError(InvalidPseudonymMapError):
    pass


@dataclass
class PseudonymMap:
    entries: dict[str, dict[str, str]] = field(
        default_factory=lambda: {
            "TARGET_COMPANY": {},
            "COMPANY": {},
            "CUSTOMER": {},
            "PERSON": {},
        }
    )
    counters: dict[str, int] = field(
        default_factory=lambda: {"COMPANY": 0, "CUSTOMER": 0, "PERSON": 0}
    )
    source_blob: bytes | None = field(default=None, repr=False, compare=False)

    @classmethod
    def from_payload(
        cls, payload: dict[str, object], source_blob: bytes | None = None
    ) -> PseudonymMap:
        entries_payload = payload.get("entries")
        counters_payload = payload.get("counters")
        entries = cls().entries
        counters = cls().counters
        if isinstance(entries_payload, dict):
            for entity_type, values in entries_payload.items():
                if entity_type not in entries or not isinstance(values, dict):
                    continue
                entries[entity_type] = {
                    str(key): str(value)
                    for key, value in values.items()
                    if isinstance(key, str) and isinstance(value, str)
                }
        if isinstance(counters_payload, dict):
            for entity_type, value in counters_payload.items():
                if entity_type in counters and isinstance(value, int):
                    counters[entity_type] = max(0, value)
        return cls(entries=entries, counters=counters, source_blob=source_blob)

    def to_payload(self) -> dict[str, object]:
        return {"version": 1, "entries": self.entries, "counters": self.counters}


@dataclass(frozen=True)
class PseudonymizationResult:
    text: str
    entities: list[PiiEntity]
    changed: bool


@dataclass(frozen=True)
class PseudonymizedPages:
    pages: list[tuple[str, int | None]]
    count: int
    entities: list[PiiEntity]
    mapping: PseudonymMap
    changed: bool


@dataclass(frozen=True)
class PseudonymizedChunkContext:
    question: str
    chunks: list[DocumentChunk]


@dataclass(frozen=True)
class _Replacement:
    start: int
    end: int
    entity_type: str
    original: str
    replacement: str | None = None


class PseudonymMapStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def load(self, tenant_id: str, matter_id: str) -> PseudonymMap:
        _validate_scope_id(tenant_id, "tenant_id")
        _validate_scope_id(matter_id, "matter_id")
        path = self._path(tenant_id, matter_id)
        if not path.exists():
            return PseudonymMap()
        return self._load_blob(tenant_id, matter_id, path.read_bytes())

    def _load_blob(
        self, tenant_id: str, matter_id: str, blob: bytes | None
    ) -> PseudonymMap:
        if blob is None:
            return PseudonymMap()
        if len(blob) <= _NONCE_BYTES:
            raise InvalidPseudonymMapError("pseudonym map is invalid")
        nonce, ciphertext = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
        try:
            plaintext = AESGCM(self._key(tenant_id, matter_id)).decrypt(nonce, ciphertext, None)
            payload = json.loads(plaintext.decode("utf-8"))
        except (InvalidTag, ValueError, UnicodeDecodeError) as exc:
            raise InvalidPseudonymMapError("pseudonym map is invalid") from exc
        if not isinstance(payload, dict):
            raise InvalidPseudonymMapError("pseudonym map is invalid")
        return PseudonymMap.from_payload(payload, source_blob=blob)

    def save(self, tenant_id: str, matter_id: str, mapping: PseudonymMap) -> None:
        _validate_scope_id(tenant_id, "tenant_id")
        _validate_scope_id(matter_id, "matter_id")
        payload = self._dump(tenant_id, matter_id, mapping)
        path = self._path(tenant_id, matter_id)
        with _scope_lock(self.settings, tenant_id, matter_id):
            current = path.read_bytes() if path.exists() else None
            if current != mapping.source_blob:
                raise PseudonymMapConflictError("pseudonym map changed during update")
            _atomic_write(path, payload)
            mapping.source_blob = payload

    def update(
        self,
        tenant_id: str,
        matter_id: str,
        mutator: Callable[[PseudonymMap], tuple[_T, bool]],
    ) -> _T:
        last_conflict: PseudonymMapConflictError | None = None
        for _ in range(_PSEUDONYM_MAP_UPDATE_ATTEMPTS):
            mapping = self.load(tenant_id, matter_id)
            result, changed = mutator(mapping)
            if not changed:
                return result
            try:
                self.save(tenant_id, matter_id, mapping)
            except PseudonymMapConflictError as exc:
                last_conflict = exc
                continue
            return result
        raise PseudonymMapConflictError("pseudonym map changed during update") from last_conflict

    def snapshot(self, tenant_id: str, matter_id: str) -> bytes | None:
        _validate_scope_id(tenant_id, "tenant_id")
        _validate_scope_id(matter_id, "matter_id")
        path = self._path(tenant_id, matter_id)
        return path.read_bytes() if path.exists() else None

    def restore(
        self,
        tenant_id: str,
        matter_id: str,
        snapshot: bytes | None,
        *,
        expected_current: bytes | None,
    ) -> None:
        _validate_scope_id(tenant_id, "tenant_id")
        _validate_scope_id(matter_id, "matter_id")
        path = self._path(tenant_id, matter_id)
        with _scope_lock(self.settings, tenant_id, matter_id):
            current = path.read_bytes() if path.exists() else None
            if current != expected_current:
                raise PseudonymMapConflictError("pseudonym map changed before restore")
            if snapshot is None:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
                return
            _atomic_write(path, snapshot)

    def remove_delta(
        self,
        tenant_id: str,
        matter_id: str,
        *,
        before: bytes | None,
        failed: bytes | None,
    ) -> None:
        if failed is None:
            return
        _validate_scope_id(tenant_id, "tenant_id")
        _validate_scope_id(matter_id, "matter_id")
        path = self._path(tenant_id, matter_id)
        with _scope_lock(self.settings, tenant_id, matter_id):
            current_blob = path.read_bytes() if path.exists() else None
            if current_blob == failed:
                if before is None:
                    try:
                        path.unlink()
                    except FileNotFoundError:
                        pass
                    return
                _atomic_write(path, before)
                return
            if current_blob is None:
                return
            before_map = self._load_blob(tenant_id, matter_id, before)
            failed_map = self._load_blob(tenant_id, matter_id, failed)
            current_map = self._load_blob(tenant_id, matter_id, current_blob)
            rebased_map = _rebase_current_without_failed_entries(
                before_map,
                failed_map,
                current_map,
            )
            if rebased_map.to_payload() != current_map.to_payload():
                payload = self._dump(tenant_id, matter_id, rebased_map)
                _atomic_write(path, payload)
                rebased_map.source_blob = payload

    def _path(self, tenant_id: str, matter_id: str) -> Path:
        return (
            self.settings.data_dir / "tenants" / tenant_id / "matters" / matter_id / "entities.enc"
        )

    def _key(self, tenant_id: str, matter_id: str) -> bytes:
        return _derive_key(self.settings.auth_secret.get_secret_value(), tenant_id, matter_id)

    def _dump(self, tenant_id: str, matter_id: str, mapping: PseudonymMap) -> bytes:
        plaintext = json.dumps(mapping.to_payload(), sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        nonce = secrets.token_bytes(_NONCE_BYTES)
        ciphertext = AESGCM(self._key(tenant_id, matter_id)).encrypt(nonce, plaintext, None)
        return nonce + ciphertext


class Pseudonymizer:
    def __init__(self, mapping: PseudonymMap, *, create_unknown_entities: bool = True) -> None:
        self.mapping = mapping
        self.create_unknown_entities = create_unknown_entities
        self.ephemeral_entries: dict[str, dict[str, str]] = {
            "TARGET_COMPANY": {},
            "COMPANY": {},
            "CUSTOMER": {},
            "PERSON": {},
        }
        self.ephemeral_counters = dict(mapping.counters)
        self.changed = False

    def pseudonymize(self, text: str) -> PseudonymizationResult:
        candidates: list[_Replacement] = []
        candidates.extend(self._detect_contextual_entities(text))
        candidates.extend(self._known_entity_replacements(text))
        selected = _select_non_overlapping(candidates)
        replacements: list[_Replacement] = []
        for candidate in selected:
            label = candidate.replacement or self._label_for(
                candidate.entity_type, candidate.original
            )
            if label is None:
                continue
            replacements.append(
                _Replacement(
                    start=candidate.start,
                    end=candidate.end,
                    entity_type=candidate.entity_type,
                    original=candidate.original,
                    replacement=label,
                )
            )
        if not replacements:
            return PseudonymizationResult(text=text, entities=[], changed=self.changed)
        updated = text
        for replacement in sorted(replacements, key=lambda item: item.start, reverse=True):
            replacement_value = replacement.replacement
            if replacement_value is None:
                continue
            updated = (
                updated[: replacement.start] + replacement_value + updated[replacement.end :]
            )
        entities: list[PiiEntity] = []
        for replacement in replacements:
            replacement_value = replacement.replacement
            if replacement_value is None:
                continue
            entities.append(
                PiiEntity(
                    entity_type=replacement.entity_type,
                    start=replacement.start,
                    end=replacement.end,
                    replacement=replacement_value,
                )
            )
        return PseudonymizationResult(text=updated, entities=entities, changed=True)

    def _detect_contextual_entities(self, text: str) -> list[_Replacement]:
        replacements: list[_Replacement] = []
        for pattern, entity_type in (
            (_PERSON_FORWARD_PATTERN, "PERSON"),
            (_PERSON_BY_PATTERN, "PERSON"),
            (_CUSTOMER_FORWARD_PATTERN, "CUSTOMER"),
            (_CUSTOMER_CONTEXT_PATTERN, "CUSTOMER"),
            (_CUSTOMER_NOUN_PATTERN, "CUSTOMER"),
        ):
            for match in pattern.finditer(text):
                replacement = self._candidate_from_match(match, entity_type)
                if replacement is not None:
                    replacements.append(replacement)
                if entity_type == "CUSTOMER":
                    replacements.extend(self._customer_chain_replacements(text, match.end("name")))
        for match in _COMPANY_PATTERN.finditer(text):
            entity_type = "TARGET_COMPANY"
            replacement = self._candidate_from_match(match, entity_type)
            if replacement is None:
                continue
            if replacement.original in _GENERIC_FALSE_POSITIVES:
                continue
            replacements.append(replacement)
        return replacements

    def _customer_chain_replacements(self, text: str, position: int) -> list[_Replacement]:
        replacements: list[_Replacement] = []
        cursor = position
        while True:
            match = _CUSTOMER_CHAIN_PATTERN.match(text, cursor)
            if match is None:
                return replacements
            replacement = self._candidate_from_match(match, "CUSTOMER")
            if replacement is not None:
                replacements.append(replacement)
            cursor = match.end("name")

    def _known_entity_replacements(self, text: str) -> list[_Replacement]:
        replacements: list[_Replacement] = []
        for entity_type, values in self.mapping.entries.items():
            for normalised, label in values.items():
                pattern = re.compile(rf"\b{re.escape(normalised)}\b", re.IGNORECASE)
                for match in pattern.finditer(text):
                    original = text[match.start() : match.end()]
                    replacements.append(
                        _Replacement(
                            start=match.start(),
                            end=match.end(),
                            entity_type=entity_type,
                            original=original,
                            replacement=label,
                        )
                    )
        return replacements

    def _candidate_from_match(
        self, match: re.Match[str], entity_type: str
    ) -> _Replacement | None:
        original = match.group("name").strip()
        if entity_type == "CUSTOMER" and _COMPANY_PATTERN.fullmatch(original):
            return None
        return _Replacement(
            start=match.start("name"),
            end=match.end("name"),
            entity_type=entity_type,
            original=original,
        )

    def _label_for(self, entity_type: str, original: str) -> str | None:
        normalised = _normalise_entity(original)
        if entity_type == "TARGET_COMPANY":
            target_entries = self.mapping.entries["TARGET_COMPANY"]
            ephemeral_targets = self.ephemeral_entries["TARGET_COMPANY"]
            if normalised in target_entries:
                return target_entries[normalised]
            if normalised in ephemeral_targets:
                return ephemeral_targets[normalised]
            if not target_entries and not ephemeral_targets:
                if not self.create_unknown_entities:
                    ephemeral_targets[normalised] = "<TARGET_COMPANY>"
                    return "<TARGET_COMPANY>"
                target_entries[normalised] = "<TARGET_COMPANY>"
                self.changed = True
                return "<TARGET_COMPANY>"
            entity_type = "COMPANY"

        entries = self.mapping.entries[entity_type]
        if normalised not in entries:
            if not self.create_unknown_entities:
                return self._ephemeral_label_for(entity_type, normalised)
            self.mapping.counters[entity_type] += 1
            entries[normalised] = f"<{entity_type}_{self.mapping.counters[entity_type]:03d}>"
            self.changed = True
        return entries[normalised]

    def _ephemeral_label_for(self, entity_type: str, normalised: str) -> str:
        entries = self.ephemeral_entries[entity_type]
        if normalised not in entries:
            self.ephemeral_counters[entity_type] += 1
            entries[normalised] = f"<{entity_type}_{self.ephemeral_counters[entity_type]:03d}>"
        return entries[normalised]


def pseudonymize_text_for_matter(
    text: str,
    *,
    settings: Settings,
    tenant_id: str,
    matter_id: str,
    create_unknown_entities: bool = True,
) -> PseudonymizationResult:
    store = PseudonymMapStore(settings)

    def apply(mapping: PseudonymMap) -> tuple[PseudonymizationResult, bool]:
        pseudonymizer = Pseudonymizer(mapping, create_unknown_entities=create_unknown_entities)
        result = pseudonymizer.pseudonymize(text)
        return result, pseudonymizer.changed

    return store.update(tenant_id, matter_id, apply)


def prepare_pseudonymized_pages_for_matter(
    pages: list[tuple[str, int | None]],
    *,
    settings: Settings,
    tenant_id: str,
    matter_id: str,
) -> PseudonymizedPages:
    store = PseudonymMapStore(settings)
    mapping = store.load(tenant_id, matter_id)
    pseudonymizer = Pseudonymizer(mapping)
    updated_pages: list[tuple[str, int | None]] = []
    entities: list[PiiEntity] = []
    for text, page in pages:
        result = pseudonymizer.pseudonymize(text)
        updated_pages.append((result.text, page))
        entities.extend(
            PiiEntity(
                entity_type=entity.entity_type,
                start=entity.start,
                end=entity.end,
                replacement=entity.replacement,
                page=page,
            )
            for entity in result.entities
        )
    return PseudonymizedPages(
        pages=updated_pages,
        count=len(entities),
        entities=entities,
        mapping=mapping,
        changed=pseudonymizer.changed,
    )


def persist_pseudonymized_pages_for_matter(
    result: PseudonymizedPages,
    *,
    settings: Settings,
    tenant_id: str,
    matter_id: str,
) -> None:
    if result.changed:
        PseudonymMapStore(settings).save(tenant_id, matter_id, result.mapping)


def snapshot_pseudonym_map_for_matter(
    *,
    settings: Settings,
    tenant_id: str,
    matter_id: str,
) -> bytes | None:
    return PseudonymMapStore(settings).snapshot(tenant_id, matter_id)


def restore_pseudonym_map_for_matter(
    snapshot: bytes | None,
    *,
    expected_current: bytes | None,
    settings: Settings,
    tenant_id: str,
    matter_id: str,
) -> None:
    PseudonymMapStore(settings).restore(
        tenant_id,
        matter_id,
        snapshot,
        expected_current=expected_current,
    )


def remove_failed_pseudonym_map_delta_for_matter(
    *,
    before: bytes | None,
    failed: bytes | None,
    settings: Settings,
    tenant_id: str,
    matter_id: str,
) -> None:
    PseudonymMapStore(settings).remove_delta(
        tenant_id,
        matter_id,
        before=before,
        failed=failed,
    )


def pseudonymize_chunks_for_matter(
    chunks: list[DocumentChunk],
    *,
    settings: Settings,
    tenant_id: str,
    matter_id: str,
) -> list[DocumentChunk]:
    store = PseudonymMapStore(settings)

    def apply(mapping: PseudonymMap) -> tuple[list[DocumentChunk], bool]:
        pseudonymizer = Pseudonymizer(mapping)
        pseudonymized = _pseudonymize_chunks(chunks, pseudonymizer)
        return pseudonymized, pseudonymizer.changed

    return store.update(tenant_id, matter_id, apply)


def pseudonymize_generation_context_for_matter(
    question: str,
    chunks: list[DocumentChunk],
    *,
    settings: Settings,
    tenant_id: str,
    matter_id: str,
) -> PseudonymizedChunkContext:
    store = PseudonymMapStore(settings)

    def apply(mapping: PseudonymMap) -> tuple[PseudonymizedChunkContext, bool]:
        source_pseudonymizer = Pseudonymizer(mapping)
        pseudonymized_chunks = _pseudonymize_chunks(chunks, source_pseudonymizer)
        query_pseudonymizer = Pseudonymizer(mapping, create_unknown_entities=False)
        pseudonymized_question = query_pseudonymizer.pseudonymize(question).text
        return (
            PseudonymizedChunkContext(
                question=pseudonymized_question,
                chunks=pseudonymized_chunks,
            ),
            source_pseudonymizer.changed,
        )

    return store.update(tenant_id, matter_id, apply)


def pseudonymize_pages_for_matter(
    pages: list[tuple[str, int | None]],
    *,
    settings: Settings,
    tenant_id: str,
    matter_id: str,
) -> tuple[list[tuple[str, int | None]], int, list[PiiEntity]]:
    result = prepare_pseudonymized_pages_for_matter(
        pages,
        settings=settings,
        tenant_id=tenant_id,
        matter_id=matter_id,
    )
    persist_pseudonymized_pages_for_matter(
        result,
        settings=settings,
        tenant_id=tenant_id,
        matter_id=matter_id,
    )
    return result.pages, result.count, result.entities


def _pseudonymize_chunks(
    chunks: list[DocumentChunk],
    pseudonymizer: Pseudonymizer,
) -> list[DocumentChunk]:
    pseudonymized: list[DocumentChunk] = []
    for chunk in chunks:
        result = pseudonymizer.pseudonymize(chunk.text)
        pseudonymized.append(chunk.model_copy(update={"text": result.text}))
    return pseudonymized


def _select_non_overlapping(replacements: list[_Replacement]) -> list[_Replacement]:
    selected: list[_Replacement] = []
    occupied: list[tuple[int, int]] = []
    for replacement in sorted(
        replacements, key=lambda item: (item.start, -(item.end - item.start))
    ):
        if any(replacement.start < end and replacement.end > start for start, end in occupied):
            continue
        selected.append(replacement)
        occupied.append((replacement.start, replacement.end))
    return selected


def _normalise_entity(value: str) -> str:
    return " ".join(value.split()).casefold()


def _rebase_current_without_failed_entries(
    before: PseudonymMap,
    failed: PseudonymMap,
    current: PseudonymMap,
) -> PseudonymMap:
    rebased = PseudonymMap.from_payload(before.to_payload())
    pseudonymizer = Pseudonymizer(rebased)
    for entity_type, current_entries in current.entries.items():
        failed_entries = failed.entries.get(entity_type, {})
        before_entries = before.entries.get(entity_type, {})
        for normalised, label in sorted(current_entries.items(), key=_placeholder_order):
            if before_entries.get(normalised) == label:
                continue
            if failed_entries.get(normalised) == label:
                continue
            pseudonymizer._label_for(
                _rebase_entity_type(entity_type, normalised, rebased),
                normalised,
            )
    return rebased


def _rebase_entity_type(
    entity_type: str,
    normalised: str,
    mapping: PseudonymMap,
) -> str:
    if (
        entity_type == "COMPANY"
        and not mapping.entries["TARGET_COMPANY"]
        and _looks_like_company_name(normalised)
    ):
        return "TARGET_COMPANY"
    return entity_type


def _looks_like_company_name(normalised: str) -> bool:
    return normalised.endswith(_COMPANY_SUFFIXES)


def _placeholder_order(item: tuple[str, str]) -> tuple[int, str]:
    normalised, label = item
    prefix, _, suffix = label.rstrip(">").rpartition("_")
    if prefix.startswith("<") and suffix.isdigit():
        return int(suffix), normalised
    return 0, normalised


def _derive_key(auth_secret: str, tenant_id: str, matter_id: str) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=_KEY_BYTES,
        salt=None,
        info=_KDF_INFO_PREFIX + f"{tenant_id}:{matter_id}".encode(),
    )
    return hkdf.derive(auth_secret.encode("utf-8"))


def validate_pseudonym_scope_ids(tenant_id: str, matter_id: str) -> None:
    _validate_scope_id(tenant_id, "tenant_id")
    _validate_scope_id(matter_id, "matter_id")


def _validate_scope_id(value: str, label: str) -> None:
    if not _ID_PATTERN.fullmatch(value):
        raise ValueError(f"{label} must match ^[A-Za-z0-9_-]{{1,64}}$")


def _scope_lock(settings: Settings, tenant_id: str, matter_id: str) -> threading.Lock:
    key = (str(settings.data_dir.resolve()), tenant_id, matter_id)
    with _PSEUDONYM_MAP_LOCKS_GUARD:
        lock = _PSEUDONYM_MAP_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _PSEUDONYM_MAP_LOCKS[key] = lock
        return lock


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".entities.enc.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
