from pathlib import Path

import pytest

from cite_or_die.core.config import Settings
from cite_or_die.core.models import DocumentChunk
from cite_or_die.security.pseudonymization import (
    InvalidPseudonymMapError,
    PseudonymMapConflictError,
    PseudonymMapStore,
    persist_pseudonymized_pages_for_matter,
    prepare_pseudonymized_pages_for_matter,
    pseudonymize_generation_context_for_matter,
    pseudonymize_pages_for_matter,
    pseudonymize_text_for_matter,
    remove_failed_pseudonym_map_delta_for_matter,
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, auth_secret="test-secret-with-at-least-32-bytes")


def test_pseudonymizes_company_customer_and_person_consistently(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    pages, count, entities = pseudonymize_pages_for_matter(
        [
            (
                "Acme Ltd generated GBP 12m revenue from Barclays. "
                "Barclays renewed. Jane Smith approved the contract.",
                1,
            )
        ],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )

    assert count == 4
    assert pages == [
        (
            "<TARGET_COMPANY> generated GBP 12m revenue from <CUSTOMER_001>. "
            "<CUSTOMER_001> renewed. <PERSON_001> approved the contract.",
            1,
        )
    ]
    assert {entity.entity_type for entity in entities} == {
        "TARGET_COMPANY",
        "CUSTOMER",
        "PERSON",
    }
    assert "GBP 12m" in pages[0][0]


def test_pseudonym_map_is_encrypted_and_reused_for_questions(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    pseudonymize_pages_for_matter(
        [
            (
                "Acme Ltd generated GBP 12m revenue from Barclays. "
                "Jane Smith approved the contract.",
                1,
            )
        ],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )

    result = pseudonymize_text_for_matter(
        "What revenue came from Barclays and who was Jane Smith?",
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )
    mapping_blob = (
        tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"
    ).read_bytes()

    assert result.text == ("What revenue came from <CUSTOMER_001> and who was <PERSON_001>?")
    assert b"Barclays" not in mapping_blob
    assert b"Jane Smith" not in mapping_blob
    assert b"Acme" not in mapping_blob


def test_read_only_question_pseudonymization_does_not_create_unknown_map(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    result = pseudonymize_text_for_matter(
        "What revenue came from Barclays, HSBC and Lloyds? "
        "Did account NatWest! Did Jane Smith approve the contract? "
        "What revenue came from Acme Ltd?",
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        create_unknown_entities=False,
    )

    assert result.text == (
        "What revenue came from <CUSTOMER_001>, <CUSTOMER_002> and <CUSTOMER_003>? "
        "Did account <CUSTOMER_004>! "
        "Did <PERSON_001> approve the contract? "
        "What revenue came from <TARGET_COMPANY>?"
    )
    assert not (
        tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"
    ).exists()


def test_read_only_question_pseudonymization_handles_customer_actions_and_dates(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    result = pseudonymize_text_for_matter(
        "Barclays generated GBP 12m revenue. "
        "What revenue came from HSBC in FY25? "
        "Lloyds and NatWest generated ARR.",
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        create_unknown_entities=False,
    )

    assert result.text == (
        "<CUSTOMER_001> generated GBP 12m revenue. "
        "What revenue came from <CUSTOMER_002> in FY25? "
        "<CUSTOMER_003> and <CUSTOMER_004> generated ARR."
    )
    assert not (
        tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"
    ).exists()


def test_read_only_question_pseudonymization_handles_customer_copula(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    result = pseudonymize_text_for_matter(
        "Revenue from Barclays was GBP 12m.",
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        create_unknown_entities=False,
    )

    assert result.text == "Revenue from <CUSTOMER_001> was GBP 12m."
    assert not (
        tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"
    ).exists()


def test_generation_context_pseudonymizes_legacy_customer_action_chunks(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    context = pseudonymize_generation_context_for_matter(
        "What revenue came from HSBC in FY25?",
        [
            DocumentChunk(
                tenant_id="tenant-a",
                matter_id="matter-a",
                doc_id="doc-a",
                chunk_id="chunk-a",
                filename="legacy.txt",
                text="Barclays generated GBP 12m revenue. Lloyds and NatWest generated ARR.",
                ordinal=0,
            )
        ],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )

    assert context.question == "What revenue came from <CUSTOMER_004> in FY25?"
    assert context.chunks[0].text == (
        "<CUSTOMER_001> generated GBP 12m revenue. "
        "<CUSTOMER_002> and <CUSTOMER_003> generated ARR."
    )


def test_read_only_question_pseudonymization_reuses_known_map_without_advancing(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    pseudonymize_pages_for_matter(
        [("Acme Ltd generated GBP 12m revenue from Barclays.", 1)],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )
    map_path = tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"
    before = map_path.read_bytes()

    result = pseudonymize_text_for_matter(
        "Compare Barclays with HSBC for Acme Ltd.",
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        create_unknown_entities=False,
    )

    assert result.text == "Compare <CUSTOMER_001> with <CUSTOMER_002> for <TARGET_COMPANY>."
    assert map_path.read_bytes() == before


def test_invalid_existing_pseudonym_map_fails_closed(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    map_path = tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"
    map_path.parent.mkdir(parents=True)
    map_path.write_bytes(b"truncated")

    with pytest.raises(InvalidPseudonymMapError):
        pseudonymize_text_for_matter(
            "What revenue came from Barclays?",
            settings=settings,
            tenant_id="tenant-a",
            matter_id="matter-a",
        )

    assert map_path.read_bytes() == b"truncated"


def test_stale_pseudonym_map_save_cannot_overwrite_newer_labels(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    first = prepare_pseudonymized_pages_for_matter(
        [("Acme Ltd generated GBP 12m revenue from Barclays.", 1)],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )
    second = prepare_pseudonymized_pages_for_matter(
        [("Acme Ltd generated GBP 8m revenue from HSBC.", 1)],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )

    persist_pseudonymized_pages_for_matter(
        first,
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )
    with pytest.raises(PseudonymMapConflictError):
        persist_pseudonymized_pages_for_matter(
            second,
            settings=settings,
            tenant_id="tenant-a",
            matter_id="matter-a",
        )
    mapping = PseudonymMapStore(settings).load("tenant-a", "matter-a")
    assert mapping.entries["CUSTOMER"] == {"barclays": "<CUSTOMER_001>"}


def test_pseudonym_map_restore_does_not_clobber_concurrent_update(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = PseudonymMapStore(settings)
    pseudonymize_pages_for_matter(
        [("Acme Ltd generated GBP 12m revenue from Barclays.", 1)],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )
    before_failed_ingest = store.snapshot("tenant-a", "matter-a")
    assert before_failed_ingest is not None
    failed_ingest = prepare_pseudonymized_pages_for_matter(
        [("Acme Ltd generated GBP 8m revenue from HSBC.", 1)],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )
    persist_pseudonymized_pages_for_matter(
        failed_ingest,
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )
    failed_state = store.snapshot("tenant-a", "matter-a")

    pseudonymize_text_for_matter(
        "What revenue came from Lloyds?",
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )
    concurrent_state = store.snapshot("tenant-a", "matter-a")

    with pytest.raises(PseudonymMapConflictError):
        store.restore(
            "tenant-a",
            "matter-a",
            before_failed_ingest,
            expected_current=failed_state,
        )
    assert store.snapshot("tenant-a", "matter-a") == concurrent_state


def test_failed_ingest_delta_rebase_reclassifies_concurrent_target_company(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    store = PseudonymMapStore(settings)
    failed_ingest = prepare_pseudonymized_pages_for_matter(
        [("Acme Ltd generated GBP 8m revenue from HSBC.", 1)],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )
    persist_pseudonymized_pages_for_matter(
        failed_ingest,
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )
    failed_state = store.snapshot("tenant-a", "matter-a")

    pseudonymize_text_for_matter(
        "Beta Ltd generated GBP 1m revenue.",
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )
    remove_failed_pseudonym_map_delta_for_matter(
        before=None,
        failed=failed_state,
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )

    mapping = store.load("tenant-a", "matter-a")
    assert mapping.entries["TARGET_COMPANY"] == {"beta ltd": "<TARGET_COMPANY>"}
    assert mapping.entries["COMPANY"] == {}
    assert mapping.entries["CUSTOMER"] == {}
