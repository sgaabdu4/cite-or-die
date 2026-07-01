from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from cite_or_die.core.config import Settings
from cite_or_die.security.pii import PiiEntity

_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_KDF_INFO_PREFIX = b"cod-pseudonym-map:"
_NONCE_BYTES = 12
_KEY_BYTES = 32
_COMPANY_PATTERN = re.compile(
    r"\b(?P<name>[A-Z][A-Za-z0-9&'.-]*(?:\s+[A-Z][A-Za-z0-9&'.-]*){0,5}\s+"
    r"(?:Ltd|Limited|PLC|plc|LLC|Inc|Corp|Corporation|Company|Group))\b"
)
_CUSTOMER_CONTEXT_PATTERN = re.compile(
    r"\b(?:from|with|for|to|by)\s+"
    r"(?P<name>[A-Z][A-Za-z0-9&'-]+(?:\s+[A-Z][A-Za-z0-9&'-]+){0,4})"
    r"(?=(?:\s+(?:generated|renewed|approved|signed|represented|accounted|contracted))?"
    r"[,.;:]|\s+(?:from|with|for|to|by)\s+|\s*$)"
)
_CUSTOMER_NOUN_PATTERN = re.compile(
    r"\b(?:customer|client|account)\s+"
    r"(?P<name>[A-Z][A-Za-z0-9&'-]+(?:\s+[A-Z][A-Za-z0-9&'-]+){0,4})"
    r"(?=[,.;:]|\s+(?:generated|renewed|approved|signed|represented|accounted)|\s*$)"
)
_PERSON_FORWARD_PATTERN = re.compile(
    r"\b(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s+"
    r"(?:approved|signed|authori[sz]ed|reviewed|requested|responded)\b"
)
_PERSON_BY_PATTERN = re.compile(
    r"\b(?:approved|signed|authori[sz]ed|reviewed|requested|responded)\s+by\s+"
    r"(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b"
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


class InvalidPseudonymMapError(RuntimeError):
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

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> PseudonymMap:
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
        return cls(entries=entries, counters=counters)

    def to_payload(self) -> dict[str, object]:
        return {"version": 1, "entries": self.entries, "counters": self.counters}


@dataclass(frozen=True)
class PseudonymizationResult:
    text: str
    entities: list[PiiEntity]
    changed: bool


@dataclass(frozen=True)
class _Replacement:
    start: int
    end: int
    entity_type: str
    original: str
    replacement: str


class PseudonymMapStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def load(self, tenant_id: str, matter_id: str) -> PseudonymMap:
        _validate_scope_id(tenant_id, "tenant_id")
        _validate_scope_id(matter_id, "matter_id")
        path = self._path(tenant_id, matter_id)
        if not path.exists():
            return PseudonymMap()
        blob = path.read_bytes()
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
        return PseudonymMap.from_payload(payload)

    def save(self, tenant_id: str, matter_id: str, mapping: PseudonymMap) -> None:
        _validate_scope_id(tenant_id, "tenant_id")
        _validate_scope_id(matter_id, "matter_id")
        plaintext = json.dumps(mapping.to_payload(), sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        nonce = secrets.token_bytes(_NONCE_BYTES)
        ciphertext = AESGCM(self._key(tenant_id, matter_id)).encrypt(nonce, plaintext, None)
        _atomic_write(self._path(tenant_id, matter_id), nonce + ciphertext)

    def _path(self, tenant_id: str, matter_id: str) -> Path:
        return (
            self.settings.data_dir / "tenants" / tenant_id / "matters" / matter_id / "entities.enc"
        )

    def _key(self, tenant_id: str, matter_id: str) -> bytes:
        return _derive_key(self.settings.auth_secret.get_secret_value(), tenant_id, matter_id)


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
        replacements: list[_Replacement] = []
        replacements.extend(self._detect_contextual_entities(text))
        replacements.extend(self._known_entity_replacements(text))
        selected = _select_non_overlapping(replacements)
        if not selected:
            return PseudonymizationResult(text=text, entities=[], changed=self.changed)
        updated = text
        for replacement in sorted(selected, key=lambda item: item.start, reverse=True):
            updated = (
                updated[: replacement.start] + replacement.replacement + updated[replacement.end :]
            )
        entities = [
            PiiEntity(
                entity_type=replacement.entity_type,
                start=replacement.start,
                end=replacement.end,
                replacement=replacement.replacement,
            )
            for replacement in selected
        ]
        return PseudonymizationResult(text=updated, entities=entities, changed=True)

    def _detect_contextual_entities(self, text: str) -> list[_Replacement]:
        replacements: list[_Replacement] = []
        for pattern, entity_type in (
            (_PERSON_FORWARD_PATTERN, "PERSON"),
            (_PERSON_BY_PATTERN, "PERSON"),
            (_CUSTOMER_CONTEXT_PATTERN, "CUSTOMER"),
            (_CUSTOMER_NOUN_PATTERN, "CUSTOMER"),
        ):
            for match in pattern.finditer(text):
                replacement = self._replacement_from_match(match, entity_type)
                if replacement is not None:
                    replacements.append(replacement)
        for match in _COMPANY_PATTERN.finditer(text):
            entity_type = "TARGET_COMPANY"
            replacement = self._replacement_from_match(match, entity_type)
            if replacement is None:
                continue
            if replacement.original in _GENERIC_FALSE_POSITIVES:
                continue
            replacements.append(replacement)
        return replacements

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

    def _replacement_from_match(
        self, match: re.Match[str], entity_type: str
    ) -> _Replacement | None:
        original = match.group("name").strip()
        if entity_type == "CUSTOMER" and _COMPANY_PATTERN.fullmatch(original):
            return None
        replacement = self._label_for(entity_type, original)
        if replacement is None:
            return None
        return _Replacement(
            start=match.start("name"),
            end=match.end("name"),
            entity_type=entity_type,
            original=original,
            replacement=replacement,
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
    mapping = store.load(tenant_id, matter_id)
    pseudonymizer = Pseudonymizer(mapping, create_unknown_entities=create_unknown_entities)
    result = pseudonymizer.pseudonymize(text)
    if pseudonymizer.changed:
        store.save(tenant_id, matter_id, mapping)
    return result


def pseudonymize_pages_for_matter(
    pages: list[tuple[str, int | None]],
    *,
    settings: Settings,
    tenant_id: str,
    matter_id: str,
) -> tuple[list[tuple[str, int | None]], int, list[PiiEntity]]:
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
    if pseudonymizer.changed:
        store.save(tenant_id, matter_id, mapping)
    return updated_pages, len(entities), entities


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
