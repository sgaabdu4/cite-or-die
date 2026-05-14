# Data Flow

1. Authenticated users upload PDF, DOCX, TXT, or Markdown sources.
2. Ingestion extracts text, redacts PII, chunks content, embeds chunks, and stores tenant/matter-scoped metadata.
3. Chat requests are normalized and scanned before retrieval.
4. Retrieval searches only the authenticated tenant/matter scope.
5. Only retrieved chunks are sent to the configured provider.
6. Returned citations are verified as substrings of retrieved chunks.
7. Audit events store allowlisted metadata and hash-chain integrity fields.

Raw document text, raw prompts, raw model outputs, provider secrets, and PII entity values are not observability attributes.
