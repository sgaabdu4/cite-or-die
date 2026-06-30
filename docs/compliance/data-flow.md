# Data Flow

1. Authenticated users upload PDF, DOCX, TXT, or Markdown sources.
2. Ingestion extracts text, redacts PII, chunks content, embeds chunks, and stores tenant/matter-scoped metadata.
3. Chat requests are normalized and scanned before retrieval.
4. Retrieval searches only the authenticated tenant/matter scope.
5. Only retrieved chunks are sent to the configured provider.
6. Returned citations are verified as substrings of retrieved chunks.
7. Diligence deal creation validates optional source document IDs inside the active tenant/matter.
8. Diligence classification and accelerator runs read only scoped matter chunks, create evidence-linked facts/findings/insights/report drafts, and store them by tenant, matter, and deal.
9. Audit events store allowlisted metadata and hash-chain integrity fields.

Raw document text, raw prompts, raw model outputs, provider secrets, PII entity values, extracted diligence facts, finding prose, vendor response text, and report draft prose are not observability attributes.
