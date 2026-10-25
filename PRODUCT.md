# cite-or-die

Ask questions about documents and receive answers with verified source quotes.

## Register

Product: a self-hosted document retrieval and citation reference application.

## Users

People reviewing documents who need source evidence and separate workspaces for confidential matters.

## Problem

An answer is unsafe to trust when its claims cannot be traced to allowed source text.

## Product Purpose

Ingest documents, retrieve tenant-scoped passages, generate answers, and verify each citation against the retrieved text. Reject or repair answers that fail verification. Support a fake provider, local models, and configured hosted providers.

## Brand Personality / Tone

Plain, direct instructions explain source evidence and privacy limits. See [README](README.md).

## Boundaries

This is not legal advice or a complete identity platform. It does not train models or guarantee provider privacy. Production hosted-model use requires explicit configuration. Tenant and matter boundaries, encrypted provider credentials, and citation verification must remain intact.

## Stack

Python FastAPI application with a browser workspace and CLI. See [dependencies](pyproject.toml), [application](app/main.py), and [runtime modules](src/cite_or_die).
