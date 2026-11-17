import { z } from "zod";
import { GatewayTransport } from "./transport.js";
export { GatewayError, GatewayBusyError } from "./transport.js";
export const clientConfig = z.object({
  url: z.url(),
  token: z.string().min(1),
  grants: z.record(z.string(), z.array(z.string())),
  protocol: z.literal("v1").default("v1"),
});
export const provisionerConfig = z
  .object({ url: z.url(), token: z.string().min(1) })
  .strict();
export type ClientConfig = z.infer<typeof clientConfig>;
export const documentSchema = z.object({
  id: z.uuid(),
  title: z.string(),
  content: z.string(),
  previousId: z.uuid().nullable().optional(),
  createdAt: z.string(),
  status: z.enum(["indexing", "ready", "unknown", "failed"]),
  version: z.number().int().positive(),
  upstreamIds: z.array(z.string()).default([]),
  contentSha256: z.string().nullable().optional(),
  errorCode: z.string().nullable().optional(),
});
export type KnowledgeDocument = z.infer<typeof documentSchema>;
export interface ImportDocument {
  id: string;
  title: string;
  content: string;
  previousId?: string;
}
const capabilitiesSchema = z.object({
  protocol_version: z.literal("knowledge-gateway/1"),
  resource_id: z.string(),
  capabilities: z.object({
    formats: z.array(z.string()),
    versions: z.boolean(),
    source: z.boolean(),
    search: z.boolean(),
    operations: z.string(),
    delete: z.boolean(),
  }),
});
const segment = encodeURIComponent;
export class KnowledgeGatewayClient {
  private readonly transport: GatewayTransport;
  constructor(
    readonly config: ClientConfig,
    readonly resourceId: string,
  ) {
    this.transport = new GatewayTransport(clientConfig.parse(config));
    if (!config.grants[resourceId]?.includes("read"))
      throw new Error("Resource is outside the client grant");
  }
  private path(suffix: string) {
    return `/v1/resources/${segment(this.resourceId)}/${suffix}`;
  }
  documents(history = false) {
    return this.transport.request(
      z.array(documentSchema),
      "GET",
      this.path(`documents?history=${history}`),
    );
  }
  document(id: string) {
    return this.transport.request(
      documentSchema,
      "GET",
      this.path(`documents/${segment(id)}`),
    );
  }
  import(value: ImportDocument) {
    return this.transport.request(
      documentSchema,
      "POST",
      this.path("documents"),
      value,
    );
  }
  capabilities() {
    return this.transport.request(
      capabilitiesSchema,
      "GET",
      this.path("capabilities"),
    );
  }
  operation(id: string) {
    return this.transport.request(
      z.object({
        operation_id: z.string(),
        document_id: z.string(),
        version: z.number(),
        status: z.enum(["processing", "completed", "failed", "unknown"]),
        error_code: z.string().nullable(),
      }),
      "GET",
      this.path(`operations/${segment(id)}`),
    );
  }
  search(query: string, limit = 5) {
    return this.transport.request(
      z.object({
        items: z.array(
          z.object({
            document_id: z.string(),
            title: z.string(),
            text: z.string(),
            version: z.number(),
            source_uri: z.string(),
            score: z.unknown().optional(),
          }),
        ),
      }),
      "POST",
      this.path("search"),
      { query, limit },
    );
  }
}
export class KnowledgeGatewayAdminClient {
  private readonly transport: GatewayTransport;
  constructor(config: z.infer<typeof provisionerConfig>) {
    this.transport = new GatewayTransport(provisionerConfig.parse(config));
  }
  provision(resourceId: string) {
    return this.transport.request(
      clientConfig,
      "PUT",
      `/admin/v1/resources/${segment(resourceId)}`,
    );
  }
}
