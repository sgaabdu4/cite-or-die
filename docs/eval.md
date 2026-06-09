# Eval Notes

Phase 1 uses a bundled 100-row T2-RAGBench financial-document subset in `examples/t2ragbench_subset.jsonl`.
The subset is a deterministic reservoir sample of the 23,088-row Hugging Face dataset with seed `20260514`.
Regenerate it with `make download-t2ragbench-subset`.

The metric shape follows RAGAS-style artifact evaluation:

- `recall_at_8 >= 0.80`
- `faithfulness >= 0.85`
- `citation_valid >= 0.95`
- `hybrid_lift_over_bm25 >= 0.15`
- measured `hybrid_lift_over_bm25_at_8`

`hybrid_lift_over_bm25` is the relative lift of hybrid recall@8 over BM25-only recall@1. `hybrid_lift_over_bm25_at_8` is reported separately to keep the BM25@8 comparison visible.

RAGAS and DeepEval currently pull LangChain packages transitively in this environment, which conflicts with the project constraint to avoid LangChain. The local gate follows the RAGAS artifact-evaluation shape without importing those packages.

BGE-M3 remains a prototype-stage embedding option. Per `goal.md`, production selection still requires MLEB verification before committing to a production embedding default.

## Benchmark Watchlist

Keep local gates deterministic and small, but use current public RAG benchmarks to shape what
the gates measure.

- T2-RAGBench remains the bundled retrieval gate because it tests RAG over real financial
  text-and-table contexts, not oracle-context QA only.
  Source: https://arxiv.org/abs/2506.12071
- RAGTruth is the best fit for hallucination-detector calibration because it labels
  retrieved-context hallucinations at response and word level across QA, summarization, and
  data-to-text tasks.
  Source: https://aclanthology.org/2024.acl-long.585
- GaRAGe is the best fit for grounding and deflection evaluation because it includes human
  grounding annotations over mixed relevant and irrelevant passages, including cases where the
  right behavior is to decline.
  Source: https://arxiv.org/abs/2506.07671

Near-term coverage target:

- Keep `tests/eval/test_t2ragbench_gate.py` for retrieval and citation validity.
- Keep verifier unit tests domain-generic: examples must span unrelated domains, not one local
  PDF or one product demo file.
- Add an offline GaRAGe/RAGTruth adapter only when we can pin a small, licensed fixture in
  `examples/` or download a deterministic subset in CI without secrets.
