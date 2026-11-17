import { z } from "zod";
export class GatewayError extends Error {
  constructor(public readonly status: number, message: string) { super(message); }
}
export class GatewayBusyError extends GatewayError {}

/** Transport owned by this module. No server error bodies or credentials escape in exceptions. */
export class GatewayTransport {
  private readonly origin: string;
  constructor(private readonly config: { url: string; token: string }) {
    const url = new URL(config.url);
    if (url.username || url.password || url.search || url.hash || url.pathname !== "/" ||
      !(url.protocol === "https:" || (url.protocol === "http:" && ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname))))
      throw new Error("Gateway URL must use HTTPS or loopback HTTP without embedded credentials or a path");
    this.origin = url.origin;
  }
  async request<S extends z.ZodType>(schema: S, method: string, path: string, body?: unknown): Promise<z.infer<S>> {
    let response: Response;
    try {
      response = await fetch(this.origin + path, { method, redirect: "error", cache: "no-store", signal: AbortSignal.timeout(45000),
        headers: { authorization: `Bearer ${this.config.token}`, ...(body === undefined ? {} : { "content-type": "application/json" }) },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
    } catch { throw new GatewayError(503, "Gateway response is unconfirmed; inspect the original operation"); }
    if (response.status === 409) throw new GatewayBusyError(409, "Original resource operation conflicts or is still unconfirmed");
    if (!response.ok) throw new GatewayError(response.status, "Gateway rejected the operation; check connection and authorization");
    try { return schema.parse(await response.json()); }
    catch { throw new GatewayError(502, "Gateway response does not match the supported protocol"); }
  }
}
