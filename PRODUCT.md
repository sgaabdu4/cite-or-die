# Product

## Register

product

## Users

Deal team analysts, managers, and advisors working inside active mid-market acquisition timelines. They need to inspect confidential deal-room documents, structured client data, vendor responses, and market context while keeping client and matter boundaries intact.

## Product Purpose

cite-or-die is evolving from a citation-verified RAG workspace into an AI-enabled Due Diligence Acceleration product. The product helps a deal team reduce diligence cycle time and improve risk visibility during a live deal cycle without weakening source traceability, confidentiality controls, or human sign-off.

The product keeps the existing evidence engine as the trust core: tenant and matter isolation, selected-source scoping, PII redaction, prompt-injection checks, verified citations, source viewing, provider controls, hosted-model production blocking, encrypted provider settings, audit hash chain, and evaluation gates remain non-negotiable.

## Implemented Surface

The current product adds a diligence workspace to the existing app shell. It can load a synthetic `Project Northstar` deal room, review selected uploaded sources, classify documents, extract key facts, produce risk findings, connect cross-workstream insights, track delayed information requests, and generate review-needed report drafts with clickable evidence links.

The main accelerator run is deterministic and local. An optional provider-assisted review can run after the baseline review, using only cited diligence evidence chunks and the configured tenant provider. Neither path produces final diligence advice, and human review mutation endpoints are not built yet.

## Product Capabilities

- Document ingest for text, PDF, and supported office-style source files, with chunking and source-file retention for evidence viewing.
- Tenant and matter isolation across upload, retrieval, selected-document scoping, source access, diligence objects, citations, and audit events.
- Provider setup for offline demo, OpenAI, Anthropic, OpenAI-compatible endpoints such as Gemini, and local Ollama, with connection testing before save.
- Provider base URL policy for OpenAI-compatible and Ollama endpoints, including local-provider exceptions, host allowlisting, and private-IP resolution blocking.
- Encrypted per-tenant provider settings; API keys are write-only in the UI and returned only as fingerprints after save.
- Hosted-model production block unless the operator explicitly enables hosted providers.
- PII redaction for detected email addresses, US SSNs, and phone numbers before chunking.
- Deterministic entity placeholdering for detected target-company, customer, company, and person names before retrieval and generation; the local tenant/matter mapping is encrypted and is not sent to model providers.
- Prompt-injection checks on model prompts and retrieved or cited evidence chunks before model generation.
- Hybrid retrieval with tenant/matter and selected-source scope, citation graph support, citation verification, and extractive repair or rejection when claims are not grounded.
- Source viewer and citation chips so every returned answer can be traced back to retrieved evidence.
- Audit hash chain with allowlisted payloads that avoid raw document text, raw prompts, raw model outputs, and API keys.
- Diligence deal workspace for commercial, operational, and financial workstreams.
- Source classification for VDR-style documents, management materials, Q&A logs, information requests, vendor responses, precedents, comparable transactions, sector benchmarks, and public information.
- Extraction review for dates, obligations, clauses, financial metrics, operational metrics, commercial metrics, information requests, and vendor responses.
- Risk and exception register for non-standard clauses, missing information, delayed responses, contradictions, concentration issues, normalisation items, materiality, confidence, owner, and status.
- Cross-workstream insight layer that connects commercial, operational, and financial evidence when dependencies span workstreams.
- Report draft view for cited workstream outputs and executive risk summaries that remain marked for review.
- Optional provider-assisted risk review that uses the configured provider, retries transient provider failures, verifies citations, stores provider metadata, returns controlled provider errors, and remains marked for human review.
- Synthetic deal-room fixture and selected-source review path for demos and regression testing.
- Evaluation, adversarial, isolation, API, UI, and browser smoke tests for the evidence and diligence paths.

## Current Limits

- Entity placeholdering protects detected names and organisations, but it does not protect every sensitive fact. Numbers, dates, contract terms, pricing, strategy, and risk content may still be sensitive if retrieved.
- Coreference is deterministic and name-based. Pronouns and indirect references such as "the customer", "it", or "they" are not fully resolved.
- The diligence accelerator creates review-needed outputs. It does not replace analyst, advisor, client, legal, tax, or investment committee judgement.
- Identity administration is not built into the app. Production deployments should use a real identity layer that issues the required tenant, matter, subject, and role claims.

## Brand Personality

Precise, controlled, and deal-paced. The product should feel like a rigorous diligence workbench: dense enough for repeated analyst use, calm enough for sensitive client work, and explicit about evidence, confidence, owner, status, and review state.

## Anti-references

- Do not present AI output as final deal judgement or a replacement for analyst, partner, advisor, client, legal, tax, or investment committee sign-off.
- Do not imply production hardening, external audit, or certifications beyond what the repo evidence proves.
- Do not add unsupported claims about finding every risk or eliminating expert review.
- Do not weaken confidentiality, tenant/matter walls, citation verification, auditability, PII redaction, prompt-injection checks, provider controls, or evaluation gates.
- Do not use marketing-style hero pages for the core app surface; users need a working deal workspace first.

## Design Principles

- Evidence before assertion: every extraction, finding, insight, and report claim must trace to source evidence.
- Human review stays visible: AI accelerates analyst workflows but never owns final sign-off.
- Cross-workstream context is the product value: commercial, operational, and financial facts should connect when siloed review would miss a dependency.
- Compressed timeline, not loose automation: workflows should support a 4-8 week live deal cycle with clear priorities, owners, and open items.
- Confidential by default: model context, logs, exports, and UI states should expose only the minimum allowed content for the active tenant and matter.

## Accessibility & Inclusion

Target WCAG 2.1 AA for new UI. Preserve keyboard navigation, visible focus, semantic labels, sufficient contrast, reduced-motion fallbacks, and readable dense tables. New diligence workflows must include empty, loading, error, permission, and review states that remain understandable without color alone.
