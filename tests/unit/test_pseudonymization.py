from pathlib import Path

from cite_or_die.core.config import Settings
from cite_or_die.security.pseudonymization import (
    pseudonymize_pages_for_matter,
    pseudonymize_text_for_matter,
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
        "What revenue came from Barclays for Acme Ltd?",
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        create_unknown_entities=False,
    )

    assert result.text == "What revenue came from Barclays for Acme Ltd?"
    assert not (
        tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"
    ).exists()


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

    assert result.text == "Compare <CUSTOMER_001> with HSBC for <TARGET_COMPANY>."
    assert map_path.read_bytes() == before
