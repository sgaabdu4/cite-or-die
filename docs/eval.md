# Eval Notes

Phase 1 uses a bundled T2-style financial-document subset in `examples/t2ragbench_subset.jsonl`.
The gate is local and deterministic so CI stays offline and does not import LangChain, LlamaIndex, or Haystack.

The metric shape follows RAGAS-style artifact evaluation:

- `recall_at_8 >= 0.80`
- `faithfulness >= 0.85`
- `citation_valid >= 0.95`
- `hybrid_lift_over_bm25 >= 0.15`

RAGAS and DeepEval currently pull LangChain packages transitively in this environment, which conflicts with the project constraint to avoid LangChain. Keep the local gate until that dependency conflict is resolved.

BGE-M3 remains a prototype-stage embedding option. Per `goal.md`, production selection still requires MLEB verification before committing to a production embedding default.
