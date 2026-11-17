# Knowledge Gateway

An independent, authorized gateway for document originals, immutable versions, indexing and source-grounded retrieval. Applications and Agents use the same REST, MCP and CLI contract. The first backend adapter uses AnythingLLM; the gateway retains originals and version references while the backend owns its index.

Actively iterating. This is a single-worker, trusted-operator deployment. It is not a new vector database, chat engine, user-account system or plugin marketplace.

## Independent quick start

Requires Python 3.11+, an AnythingLLM developer API and an existing embedding configuration. Install this package and prepare private local credentials:

```sh
pip install .
knowledge-gateway-admin --policy .local/policy.json init
knowledge-gateway-admin --policy .local/policy.json resource notes --namespace notes --connection anythingllm
knowledge-gateway-admin --policy .local/policy.json issue --name agent --read notes --write notes --url http://127.0.0.1:3333 --output .local/client.json
```

Create `.local/connections.json` using the example in `examples/`. Keep the token and policy files private. Set `KNOWLEDGE_POLICY`, `KNOWLEDGE_CONNECTIONS_FILE` and `KNOWLEDGE_STATE` to absolute private paths. Then run:

```sh
uvicorn knowledge_gateway.app:app --host 127.0.0.1 --port 3333 --no-access-log
knowledge-gateway --config .local/client.json resources
knowledge-gateway --config .local/client.json import notes 6f3f85df-e157-4642-9198-077826d30e64 --title Example --file ./example.md
knowledge-gateway --config .local/client.json operation notes 6f3f85df-e157-4642-9198-077826d30e64
knowledge-gateway --config .local/client.json search notes 'your question'
knowledge-gateway --config .local/client.json source notes 6f3f85df-e157-4642-9198-077826d30e64
```

Choose your own stable UUID before each import. To create a new version, use a new UUID and `--previous-id` referencing the current document. Each cited document ID keeps its original text. After a timeout, observe the original ID; do not create a new import to hide an unknown outcome.

## Protocol and clients

- REST: `/v1/resources`, resource capabilities, documents, search and operations; OpenAPI at `/openapi.json`.
- MCP: `/mcp/`, using a resource-scoped bearer token; discovery, import, search, source and operation tools.
- TypeScript: `sdk/`, package `@hutian-ai/knowledge-gateway-client`; run `pnpm install && pnpm build` there. The SDK owns domain types and response validation.
- CLI: `knowledge-gateway` uses the same authorization and resource semantics.

See [PROTOCOL.md](PROTOCOL.md) for version and error semantics. Ordinary tokens cannot provision resources. An operator can opt into `/admin/v1/resources/{id}` using `KNOWLEDGE_ADMIN_CONFIG`; the host credential is separate, restricted to an operator-selected identifier pattern, connection and grants. It never accepts backend paths, tokens or namespace overrides from a request.

## Storage and adoption

`KNOWLEDGE_STATE/libraries/<namespace>` stores originals. Operator policy may explicitly bind a resource to an existing library directory and source URI prefix. This preserves original document IDs, versions and index associations; startup does not copy documents or re-index them. Every resource owns a distinct backend namespace. Runtime reads check current grants and revocations.

Statuses distinguish `indexing`, `ready`, `failed` and `unknown`. Only ready current versions participate in retrieval. An interrupted index request becomes unknown on observation; the original source remains readable. A failed or unknown version does not replace the previous ready version. This release does not implement automatic index repair, PDF parsing, cross-backend migration, deletion or arbitrary multi-worker operation.

## Hutian integration

Hutian's server plugin maps its authorized member/conversation/workspace resource to a scoped gateway client. Hutian owns people, grants and context selection; this module owns sources, versions and index adapters. It can be used without Hutian or Memory Gateway.

No npm, PyPI or container registry release has been published for this source delivery.
