# Source delivery — 2026-11-17

Knowledge Gateway is an independent repository with a REST API, MCP, CLI and TypeScript SDK. Markdown originals, immutable version IDs, status, citations and the AnythingLLM adapter belong here. Host applications supply authorized opaque resource IDs, not people, room models or backend credentials.

## Observed checks

- Standalone SDK import indexed a document, retrieved it with its source, imported a second version, and preserved the first version byte-for-byte. Reusing the same ID/input observed the original result instead of importing again.
- An initial index connection failure retained its original source as `unknown`; it was not silently retried. The corrected connection was checked with a separate, explicitly identified acceptance import.
- MCP exposes six tools and read the same original. Cross-resource access and ordinary-token administration returned 403; a read-only credential could not write, and revocation denied its next read.
- Hutian adopted six existing originals through explicit operator library bindings, preserving IDs, version chains, content hashes and index associations without re-importing.
- Hutian's knowledge page saved, retrieved and linked a new source. A real Mac member chat searched it and read the original. Historical source links preserve the cited version.
- SDK build, Python compilation and the consuming application's relevant TypeScript checks/builds passed. No test framework or test suite was added.

The package is running locally in a persistent Docker service alongside the original AnythingLLM instance. Source delivery uses the private `hutian-ai/knowledge-gateway` repository. There is no npm/PyPI or container registry release from this work. Private evidence is kept in the adjacent workspace's `.local/gateway-acceptance-20261117/`, not in this repository.

## Limits

Markdown and the existing AnythingLLM adapter only. One application worker/process; no claim of multi-worker coordination, automatic repair, exactly-once remote indexing, PDF parsing, deletion or cross-backend migration. An `unknown` result stays observable by its original ID. A ready version does not make old citations point to new text. Host management is opt-in with a separate operator-issued credential.

Use [README.md](README.md) for independent installation and [PROTOCOL.md](PROTOCOL.md) for the contract. Hutian's explicit adoption and restore procedure lives in its own integration documentation, not in this module's business protocol.
