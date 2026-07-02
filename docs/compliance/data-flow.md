# Data Flow

1. Authenticated users upload PDF, DOCX, TXT, or Markdown sources.
2. Ingestion extracts text, stores the original source file, pseudonymizes detected target-company/customer/company/person names, redacts detected PII, writes a pseudonymized evidence preview, chunks content, embeds chunks, and stores tenant/matter-scoped metadata.
3. Chat requests are normalized and scanned before retrieval.
4. Retrieval searches only the authenticated tenant/matter scope.
5. Only retrieved chat chunks are sent to the configured provider; hosted-provider context must pass entity-placeholder and residual-entity checks first.
6. Returned chat citations are verified as substrings of retrieved chunks.
7. Source preview uses `/docs/{doc_id}/file` for pseudonymized text evidence; `/docs/{doc_id}/raw` returns the authorized original file.
8. Diligence deal creation validates optional source document IDs inside the active tenant/matter.
9. Diligence classification and accelerator runs read only scoped matter chunks, create evidence-linked facts/findings/insights/report drafts, and store them by tenant, matter, and deal.
10. Optional provider-assisted diligence runs only after the baseline review, sends pseudonymized cited diligence evidence chunks through the configured provider after prompt and retrieved-content guardrails, and stores only verified cited report claims.
11. Audit events store allowlisted metadata and hash-chain integrity fields.

Raw document text, raw prompts, raw model outputs, provider secrets, PII entity values, extracted diligence facts, finding prose, vendor response text, and report draft prose are not observability attributes.
