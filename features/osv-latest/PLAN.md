# Latest secure dependencies and local reranking

Status: Complete

## Outcome + scope

Update affected dependencies to their latest stable versions while retaining local BGE embeddings and reranking.

## Repository context

Owners: pyproject.toml, uv.lock, src/cite_or_die/retrieval/rerank.py and tests/unit/test_reranker.py. Restore the retired Hard Eng installation while retaining existing CI checks.
Same cause: The optional FlagEmbedding dependency requires datasets, which caps fsspec below its latest release. Sentence Transformers already provides embeddings and supports the same BGE reranker model through CrossEncoder, as documented by the [model owner](https://huggingface.co/BAAI/bge-reranker-v2-m3) and [CrossEncoder reference](https://sbert.net/docs/package_reference/cross_encoder/model.html).

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: The user requested all vulnerabilities fixed, latest stable releases merged to main, and explicitly chose changing local-model support to permit latest dependencies. Existing local model names and capabilities remain. The personal one-PR rule requires prerequisite repairs and dependency updates in one product PR; both plans retain their separate evidence.

## Acceptance + steps

- [x] Latest affected releases resolve and OSV reports no vulnerabilities. N/A — native lock resolution and vulnerability scanning verify dependency metadata.
- [x] BGE reranking uses the same model, raw score scale and result ordering, proved by `tests/unit/test_reranker.py::test_bge_reranker_preserves_raw_scores_without_flagembedding`.
- [x] Existing tests and required restored gates pass without reducing their checks. N/A — the complete native gate verifies the configured check inventory.
- [x] The demo recorder creates a playable offline upload/chat/citation video and stops its server, proved by `scripts/record_demo/tests/record.test.ts::records the offline upload and citation journey and stops its server`.

## Baseline + execution

Result: Passed
Evidence: The initial baseline failed: the retired pinned checker release returned HTTP 404, and restored strict static and workflow checks exposed defects. The supported installation preserves existing CI commands. After repairs, the full gate passed 111 Python tests, both recorder tests, performance, evaluations, security and workflow checks. Its sole remaining diagnostic was a deprecated load-server lifespan annotation; the focused type recheck passed after correction. The gate-repair plan retains the initial failures and detailed repair proof.
Execution: One owner repairs dependency resolution and local model adapter, then checks existing behavior and all required gates.

## Risks + recovery

Retain raw logits and float32 model behavior to avoid changing score thresholds. Existing Git history preserves the prior implementation. The demo package's recording test launches the Python application, so its dependency mapping includes the root package. Recording tests write only to temporary data and video paths. Automated benchmarks and load tests enforce the existing goal.md budgets for the default local pipeline. Production model latency is not validated. The recorder alone has a reviewed native performance exception because its paced offline video generation has no service latency target.

## ux_reference

N/A — dependency and model adapter changes retain the existing commands and interface.

## Verification

Result: Passed
Evidence: The final full native Ready gate passed after the annotation and CI check-name corrections. It covered 111 Python tests, both recorder tests, performance, existing evaluations, all static checks, release checks and security scans. OSV scanned 226 Python and seven recorder package records with no vulnerabilities. Reranker regression tests failed before the adapter change and all six passed after it. A real CrossEncoder check with a locally generated tiny classifier preserved direct raw logits for single and multiple pairs, and returned no results for empty input. The full BAAI weights were not downloaded or benchmarked. Both recorder tests passed after correcting the obsolete citation selector. Chromium completed upload, chat and source opening; ffprobe confirmed a playable H264 video at 1280 by 760, and the server stopped.
E2E: Passed — existing upload, retrieval, chat, citation and tenant tests passed. The real browser recorder completed upload, chat and source opening, generated playable video and stopped its server. BGE adapter tests retained empty, single and multiple-hit behavior.

Delivery target: Merge
Delivery: Pending — required pull request checks and protected merge.
