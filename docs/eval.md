# Eval Notes

Phase 1 uses a bundled 100-row T2-RAGBench financial-document subset in `examples/t2ragbench_subset.jsonl`.
The subset is a deterministic reservoir sample of the 23,088-row Hugging Face dataset with seed `20260514`.
Regenerate it with `make download-t2ragbench-subset`.

The metric shape follows RAGAS-style artifact evaluation:

- `recall_at_8 >= 0.80`
- `faithfulness >= 0.85`
- `citation_valid >= 0.95`
- measured `hybrid_lift_over_bm25`

RAGAS and DeepEval currently pull LangChain packages transitively in this environment, which conflicts with the project constraint to avoid LangChain. The local gate follows the RAGAS artifact-evaluation shape without importing those packages.

BGE-M3 remains a prototype-stage embedding option. Per `goal.md`, production selection still requires MLEB verification before committing to a production embedding default.
The Phase 1 tag remains blocked until a real BGE-M3 plus BGE-reranker run clears `hybrid_lift_over_bm25 >= 0.15`.
