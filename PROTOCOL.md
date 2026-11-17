# Knowledge Gateway protocol 1

A module contract, not an industry standard. Discovery is `knowledge-gateway/1`; REST uses `/v1`. REST, MCP and CLI invoke the same application methods.

| Operation | HTTP | Meaning |
| --- | --- | --- |
| Resources | GET /v1/resources | Discover granted resource IDs |
| Capabilities | GET /v1/resources/{resource}/capabilities | Formats and supported operations |
| Import | POST /v1/resources/{resource}/documents | Store original, index and return observed state |
| List | GET /v1/resources/{resource}/documents?history=true | Include immutable historical versions when requested |
| Source | GET /v1/resources/{resource}/documents/{id} | Read a specific original and its version |
| Search | POST /v1/resources/{resource}/search | Return fragments with document ID, version and source URI |
| Observe | GET /v1/resources/{resource}/operations/{id} | Observe the original import without replay |

Imports contain UUID `id`, `title`, Markdown `content`, and optional `previousId`. Reusing an ID requires identical input and returns the original record. A new version uses a new ID and a predecessor in the same resource. An already superseded or unconfirmed predecessor cannot silently branch. Originals are durable before index mutation. Backend 4xx rejection is failed; lost/partial responses are unknown. No unknown operation is automatically replayed.

Resource grants apply to discovery, import, list, search, source and operation observation. The operator maps each resource to a unique index namespace and private original directory. Source URIs and retrieved text never grant permissions. Provider credentials and filesystem paths never appear in ordinary results or errors. Scores are provider-local and do not imply factual accuracy.

The caller receives immutable document IDs and versions, not World-specific page links. The host may construct its own authorized links. Indexes are derived; original sources and version references remain authoritative. The initial adapter supports Markdown through AnythingLLM; capability discovery explicitly marks deletion unsupported.

HTTP 401/403 deny access; 404 means no document in the authorized resource; 409 rejects conflicting input/version transitions; 5xx means the service could not confirm a result. Unknown and failed imports retain readable originals. `operation.status` maps ready to completed and indexing to processing. A process-interrupted indexing record is observed as unknown.
