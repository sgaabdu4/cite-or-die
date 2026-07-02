from pathlib import Path

import pytest

from cite_or_die.core.config import Settings
from cite_or_die.core.models import DocumentChunk
from cite_or_die.security.pseudonymization import (
    InvalidPseudonymMapError,
    PseudonymMapConflictError,
    PseudonymMapStore,
    ResidualPseudonymizationError,
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
        "Did Barclays generate revenue? "
        "Has Barclays generated revenue? "
        "Barclays generates ARR. "
        "What revenue came from HSBC in FY25? "
        "Lloyds and NatWest generated ARR. "
        "3M generated ARR.",
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        create_unknown_entities=False,
    )

    assert result.text == (
        "<CUSTOMER_001> generated GBP 12m revenue. "
        "Did <CUSTOMER_001> generate revenue? "
        "Has <CUSTOMER_001> generated revenue? "
        "<CUSTOMER_001> generates ARR. "
        "What revenue came from <CUSTOMER_002> in FY25? "
        "<CUSTOMER_003> and <CUSTOMER_004> generated ARR. "
        "<CUSTOMER_005> generated ARR."
    )
    assert not (
        tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"
    ).exists()


def test_read_only_question_pseudonymization_handles_bare_identity_questions(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    result = pseudonymize_text_for_matter(
        "Who is Jane Smith? Tell me about Barclays.",
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        create_unknown_entities=False,
    )

    assert result.text == "Who is <PERSON_001>? Tell me about <CUSTOMER_001>."
    context = pseudonymize_generation_context_for_matter(
        "Who is Jane Smith? Tell me about Barclays.",
        [],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        require_complete_pseudonymization=True,
    )
    assert context.question == "Who is <PERSON_001>? Tell me about <CUSTOMER_001>."
    assert not (
        tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"
    ).exists()


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Jane Smith?", "<PERSON_001>?"),
        ("Barclays?", "<CUSTOMER_001>?"),
    ],
)
def test_generation_context_pseudonymizes_bare_entity_prompts_for_hosted(
    tmp_path: Path,
    question: str,
    expected: str,
) -> None:
    settings = _settings(tmp_path)

    context = pseudonymize_generation_context_for_matter(
        question,
        [],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        require_complete_pseudonymization=True,
    )

    assert context.question == expected
    assert not (
        tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"
    ).exists()


@pytest.mark.parametrize(
    "question",
    ["Gross Margin?", "Revenue?", "ARR?", "Sales Pipeline?", "Net Revenue?", "RAG?"],
)
def test_read_only_question_pseudonymization_ignores_bare_diligence_topics(
    tmp_path: Path,
    question: str,
) -> None:
    settings = _settings(tmp_path)

    result = pseudonymize_text_for_matter(
        question,
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        create_unknown_entities=False,
    )
    context = pseudonymize_generation_context_for_matter(
        question,
        [],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        require_complete_pseudonymization=True,
    )

    assert result.text == question
    assert context.question == question
    assert not (
        tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"
    ).exists()


def test_read_only_question_pseudonymization_handles_customer_metric_subjects(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    result = pseudonymize_text_for_matter(
        "Barclays revenue was GBP 12m. "
        "HSBC's revenue grew. "
        "Barclays' revenue expanded. "
        "Bank of America generated ARR.",
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        create_unknown_entities=False,
    )

    assert result.text == (
        "<CUSTOMER_001> revenue was GBP 12m. "
        "<CUSTOMER_002>'s revenue grew. "
        "<CUSTOMER_001>' revenue expanded. "
        "<CUSTOMER_003> generated ARR."
    )
    assert not (
        tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"
    ).exists()


def test_financial_periods_are_not_customer_metric_subjects(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    pages, count, _entities = pseudonymize_pages_for_matter(
        [
            (
                "FY26 revenue is GBP 180m. "
                "Q1 revenue was GBP 20m. "
                "LTM revenue was GBP 90m. "
                "Total revenue was GBP 100m. "
                "Barclays revenue was GBP 12m.",
                1,
            )
        ],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )

    assert count == 0
    assert pages == [
        (
            "FY26 revenue is GBP 180m. "
            "Q1 revenue was GBP 20m. "
            "LTM revenue was GBP 90m. "
            "Total revenue was GBP 100m. "
            "Barclays revenue was GBP 12m.",
            1,
        )
    ]
    mapping = PseudonymMapStore(settings).load("tenant-a", "matter-a")
    assert mapping.entries["CUSTOMER"] == {}


def test_commercial_metric_labels_are_not_customer_metric_subjects(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    pages, count, _entities = pseudonymize_pages_for_matter(
        [
            (
                "Customer churn is 16 percent. "
                "Sales pipeline was GBP 20m. "
                "Client retention improved. "
                "Contract renewal was delayed. "
                "Account retention improved. "
                "Subscription revenue increased. "
                "Services revenue was GBP 12m. "
                "Professional Services revenue grew. "
                "Product ARR improved.",
                1,
            )
        ],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )

    assert count == 0
    assert pages == [
        (
            "Customer churn is 16 percent. "
            "Sales pipeline was GBP 20m. "
            "Client retention improved. "
            "Contract renewal was delayed. "
            "Account retention improved. "
            "Subscription revenue increased. "
            "Services revenue was GBP 12m. "
            "Professional Services revenue grew. "
            "Product ARR improved.",
            1,
        )
    ]
    mapping = PseudonymMapStore(settings).load("tenant-a", "matter-a")
    assert mapping.entries["CUSTOMER"] == {}


def test_metric_subjects_require_stronger_customer_context_to_persist(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    pages, count, _entities = pseudonymize_pages_for_matter(
        [
            (
                "New Logo revenue was GBP 12m. "
                "Enterprise revenue grew. "
                "Marks & Spencer revenue improved. "
                "J.P. Morgan revenue improved. "
                "eBay revenue improved. "
                "3M revenue improved.",
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
            "New Logo revenue was GBP 12m. "
            "Enterprise revenue grew. "
            "<CUSTOMER_001> revenue improved. "
            "<CUSTOMER_002> revenue improved. "
            "<CUSTOMER_003> revenue improved. "
            "<CUSTOMER_004> revenue improved.",
            1,
        )
    ]
    mapping = PseudonymMapStore(settings).load("tenant-a", "matter-a")
    assert mapping.entries["CUSTOMER"] == {
        "marks & spencer": "<CUSTOMER_001>",
        "j.p. morgan": "<CUSTOMER_002>",
        "ebay": "<CUSTOMER_003>",
        "3m": "<CUSTOMER_004>",
    }


def test_hosted_generation_ephemerally_pseudonymizes_ambiguous_metric_subjects(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    context = pseudonymize_generation_context_for_matter(
        "Barclays revenue?",
        [
            DocumentChunk(
                tenant_id="tenant-a",
                matter_id="matter-a",
                doc_id="doc-a",
                chunk_id="chunk-a",
                filename="legacy.txt",
                text="Barclays revenue was GBP 12m. New Logo revenue was GBP 3m.",
                ordinal=0,
            )
        ],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        require_complete_pseudonymization=True,
    )

    assert context.question == "<CUSTOMER_001> revenue?"
    assert context.chunks[0].text == (
        "<CUSTOMER_001> revenue was GBP 12m. <CUSTOMER_002> revenue was GBP 3m."
    )
    assert not (
        tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"
    ).exists()


def test_read_only_question_pseudonymization_handles_person_third_person_actions(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    result = pseudonymize_text_for_matter(
        "Jane Smith signs the contract. "
        "John Doe reviews the contract. "
        "Mary Jones requests approval. "
        "Sam Adams responds today.",
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        create_unknown_entities=False,
    )

    assert result.text == (
        "<PERSON_001> signs the contract. "
        "<PERSON_002> reviews the contract. "
        "<PERSON_003> requests approval. "
        "<PERSON_004> responds today."
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


def test_generation_context_pseudonymizes_dotted_customer_and_middle_initial_person(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    context = pseudonymize_generation_context_for_matter(
        "Did Jane A. Smith approve revenue from J.P. Morgan?",
        [
            DocumentChunk(
                tenant_id="tenant-a",
                matter_id="matter-a",
                doc_id="doc-a",
                chunk_id="chunk-a",
                filename="legacy.txt",
                text="Revenue from J.P. Morgan was GBP 12m. Jane A. Smith approved the contract.",
                ordinal=0,
            )
        ],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )

    assert context.question == "Did <PERSON_001> approve revenue from <CUSTOMER_001>?"
    assert context.chunks[0].text == (
        "Revenue from <CUSTOMER_001> was GBP 12m. "
        "<PERSON_001> approved the contract."
    )


def test_generation_context_pseudonymizes_punctuation_person_names(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    context = pseudonymize_generation_context_for_matter(
        "Did Sarah O'Neil approve the contract?",
        [
            DocumentChunk(
                tenant_id="tenant-a",
                matter_id="matter-a",
                doc_id="doc-a",
                chunk_id="chunk-a",
                filename="legacy.txt",
                text=(
                    "Sarah O'Neil approved the contract. "
                    "Mary-Jane Smith approved the renewal."
                ),
                ordinal=0,
            )
        ],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        require_complete_pseudonymization=True,
    )

    assert context.question == "Did <PERSON_001> approve the contract?"
    assert context.chunks[0].text == (
        "<PERSON_001> approved the contract. <PERSON_002> approved the renewal."
    )


def test_generation_context_pseudonymizes_person_names_with_particles(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    context = pseudonymize_generation_context_for_matter(
        "Did John van der Meer approve the contract?",
        [
            DocumentChunk(
                tenant_id="tenant-a",
                matter_id="matter-a",
                doc_id="doc-a",
                chunk_id="chunk-a",
                filename="legacy.txt",
                text="John van der Meer approved the contract.",
                ordinal=0,
            )
        ],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        require_complete_pseudonymization=True,
    )

    assert context.question == "Did <PERSON_001> approve the contract?"
    assert context.chunks[0].text == "<PERSON_001> approved the contract."


def test_generation_context_pseudonymizes_mixed_case_customer_brands(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    context = pseudonymize_generation_context_for_matter(
        "Did eBay generate ARR?",
        [
            DocumentChunk(
                tenant_id="tenant-a",
                matter_id="matter-a",
                doc_id="doc-a",
                chunk_id="chunk-a",
                filename="legacy.txt",
                text="eBay generated ARR. easyJet generated revenue.",
                ordinal=0,
            )
        ],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        require_complete_pseudonymization=True,
    )

    assert context.question == "Did <CUSTOMER_001> generate ARR?"
    assert context.chunks[0].text == (
        "<CUSTOMER_001> generated ARR. <CUSTOMER_002> generated revenue."
    )


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


def test_generation_context_residual_guard_rejects_person_lists(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)

    with pytest.raises(ResidualPseudonymizationError) as exc:
        pseudonymize_generation_context_for_matter(
            "Participants: Jane Smith and John Doe",
            [],
            settings=settings,
            tenant_id="tenant-a",
            matter_id="matter-a",
            require_complete_pseudonymization=True,
        )

    assert str(exc.value) == "Hosted generation context contains unprotected entity names."
    assert not (
        tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"
    ).exists()


@pytest.mark.parametrize(
    ("chunk_text", "expected"),
    [
        ("Jane Smith?", "<PERSON_001>?"),
        ("Barclays?", "<CUSTOMER_001>?"),
    ],
)
def test_generation_context_pseudonymizes_bare_entity_chunks_for_hosted(
    tmp_path: Path,
    chunk_text: str,
    expected: str,
) -> None:
    settings = _settings(tmp_path)

    context = pseudonymize_generation_context_for_matter(
        "What changed?",
        [
            DocumentChunk(
                tenant_id="tenant-a",
                matter_id="matter-a",
                doc_id="doc-a",
                chunk_id="chunk-a",
                filename="legacy.txt",
                text=chunk_text,
                ordinal=0,
            )
        ],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        require_complete_pseudonymization=True,
    )

    assert context.chunks[0].text == expected
    assert not (
        tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"
    ).exists()


def test_generation_context_residual_guard_rejects_unlabelled_person_question(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)

    with pytest.raises(ResidualPseudonymizationError):
        pseudonymize_generation_context_for_matter(
            "Was Jane Smith involved?",
            [],
            settings=settings,
            tenant_id="tenant-a",
            matter_id="matter-a",
            require_complete_pseudonymization=True,
        )

    assert not (
        tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"
    ).exists()


def test_generation_context_residual_guard_rejects_unlabelled_person_action(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)

    with pytest.raises(ResidualPseudonymizationError):
        pseudonymize_generation_context_for_matter(
            "Did Jane Smith attend the meeting?",
            [],
            settings=settings,
            tenant_id="tenant-a",
            matter_id="matter-a",
            require_complete_pseudonymization=True,
        )

    assert not (
        tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"
    ).exists()


def test_generation_context_residual_guard_allows_unlabelled_title_case_terms(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    context = pseudonymize_generation_context_for_matter(
        "summarise revenue and gross margin.",
        [
            DocumentChunk(
                tenant_id="tenant-a",
                matter_id="matter-a",
                doc_id="doc-a",
                chunk_id="chunk-a",
                filename="legacy.txt",
                text=(
                    "Revenue and Gross Margin were reported. "
                    "Terms and Conditions were reviewed."
                ),
                ordinal=0,
            )
        ],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        require_complete_pseudonymization=True,
    )

    assert context.question == "summarise revenue and gross margin."
    assert context.chunks[0].text == (
        "Revenue and Gross Margin were reported. Terms and Conditions were reviewed."
    )


def test_generation_context_residual_guard_allows_document_status_titles(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    context = pseudonymize_generation_context_for_matter(
        "summarise supplier documents.",
        [
            DocumentChunk(
                tenant_id="tenant-a",
                matter_id="matter-a",
                doc_id="doc-a",
                chunk_id="chunk-a",
                filename="legacy.txt",
                text=(
                    "Vendor Response is a key supplier document. "
                    "Acquisition Materials is a key supplier document. "
                    "Board Pack is a key customer document."
                ),
                ordinal=0,
            )
        ],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        require_complete_pseudonymization=True,
    )

    assert context.chunks[0].text == (
        "Vendor Response is a key supplier document. "
        "Acquisition Materials is a key supplier document. "
        "Board Pack is a key customer document."
    )


def test_generation_context_residual_guard_rejects_unlabelled_customer_status(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)

    with pytest.raises(ResidualPseudonymizationError):
        pseudonymize_generation_context_for_matter(
            "What customers matter?",
            [
                DocumentChunk(
                    tenant_id="tenant-a",
                    matter_id="matter-a",
                    doc_id="doc-a",
                    chunk_id="chunk-a",
                    filename="legacy.txt",
                    text="Barclays is a key customer.",
                    ordinal=0,
                )
            ],
            settings=settings,
            tenant_id="tenant-a",
            matter_id="matter-a",
            require_complete_pseudonymization=True,
        )


def test_generation_context_residual_guard_rejects_unmatched_customer_actions(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)

    with pytest.raises(ResidualPseudonymizationError):
        pseudonymize_generation_context_for_matter(
            "What happened with the renewal?",
            [
                DocumentChunk(
                    tenant_id="tenant-a",
                    matter_id="matter-a",
                    doc_id="doc-a",
                    chunk_id="chunk-a",
                    filename="legacy.txt",
                    text="Barclays cancelled the renewal.",
                    ordinal=0,
                )
            ],
            settings=settings,
            tenant_id="tenant-a",
            matter_id="matter-a",
            require_complete_pseudonymization=True,
        )


def test_generation_context_residual_guard_rejects_customer_pricing_action(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)

    with pytest.raises(ResidualPseudonymizationError):
        pseudonymize_generation_context_for_matter(
            "What changed?",
            [
                DocumentChunk(
                    tenant_id="tenant-a",
                    matter_id="matter-a",
                    doc_id="doc-a",
                    chunk_id="chunk-a",
                    filename="legacy.txt",
                    text="Barclays increased pricing.",
                    ordinal=0,
                )
            ],
            settings=settings,
            tenant_id="tenant-a",
            matter_id="matter-a",
            require_complete_pseudonymization=True,
        )


def test_generation_context_residual_guard_is_opt_in_for_local_generation(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    context = pseudonymize_generation_context_for_matter(
        "Participants: Jane Smith and John Doe",
        [
            DocumentChunk(
                tenant_id="tenant-a",
                matter_id="matter-a",
                doc_id="doc-a",
                chunk_id="chunk-a",
                filename="legacy.txt",
                text="Barclays cancelled the renewal.",
                ordinal=0,
            )
        ],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )

    assert context.question == "Participants: Jane Smith and John Doe"
    assert context.chunks[0].text == "Barclays cancelled the renewal."


def test_generation_context_pseudonymizes_ampersand_customer_names_for_hosted(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    context = pseudonymize_generation_context_for_matter(
        "What did Marks & Spencer generate?",
        [
            DocumentChunk(
                tenant_id="tenant-a",
                matter_id="matter-a",
                doc_id="doc-a",
                chunk_id="chunk-a",
                filename="legacy.txt",
                text="Marks & Spencer generated ARR.",
                ordinal=0,
            )
        ],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
        require_complete_pseudonymization=True,
    )

    assert context.question == "What did <CUSTOMER_001> generate?"
    assert context.chunks[0].text == "<CUSTOMER_001> generated ARR."


def test_document_titles_are_not_pseudonymized_as_people(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    pages, count, _entities = pseudonymize_pages_for_matter(
        [
            (
                "Board Meeting approved the budget. "
                "Information Request approved the item.",
                1,
            )
        ],
        settings=settings,
        tenant_id="tenant-a",
        matter_id="matter-a",
    )

    assert count == 0
    assert pages == [
        (
            "Board Meeting approved the budget. "
            "Information Request approved the item.",
            1,
        )
    ]
    mapping = PseudonymMapStore(settings).load("tenant-a", "matter-a")
    assert mapping.entries["PERSON"] == {}
    assert mapping.entries["CUSTOMER"] == {}


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
