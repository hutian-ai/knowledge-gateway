"""Index adapters. Documents and their stable versions are owned by the gateway."""
from urllib.parse import quote
from typing import Protocol
import httpx
from .policy import AccessDenied


class IndexProvider(Protocol):
    async def index(self, namespace: str, document: dict, source_uri: str) -> list[str]: ...
    async def search(self, namespace: str, query: str, limit: int) -> list[dict]: ...


class IndexRejected(Exception):
    """A definite rejection, rather than a connection failure with unknown effects."""


class AnythingLLM:
    def __init__(self, config):
        self.url, self.token = config["url"].rstrip("/"), config["token"]

    async def request(self, method, path, body=None):
        try:
            async with httpx.AsyncClient(timeout=40, follow_redirects=False) as client:
                response = await client.request(method, self.url + path, json=body,
                                                headers={"Authorization": "Bearer " + self.token})
        except httpx.RequestError:
            raise AccessDenied(503, "Index response unconfirmed; observe the original document") from None
        if response.status_code in (400, 401, 403, 404, 409, 413, 422):
            raise IndexRejected("Index rejected the request")
        if not response.is_success:
            raise AccessDenied(503, "Index response unconfirmed; observe the original document")
        try:
            return response.json()
        except ValueError:
            raise AccessDenied(502, "Index returned an invalid response") from None

    async def index(self, namespace, document, source_uri):
        workspace = await self.request("GET", "/api/v1/workspace/" + quote(namespace, safe=""))
        if not workspace.get("workspace"):
            await self.request("POST", "/api/v1/workspace/new", {"name": namespace})
        result = await self.request("POST", "/api/v1/document/raw-text", {
            "textContent": document["content"], "addToWorkspaces": namespace,
            "metadata": {"title": document["id"] + ".md", "docSource": source_uri, "description": document["title"]}})
        if not result.get("success"):
            # A negative response may follow a partial index write; never pretend it had no effect.
            raise AccessDenied(503, "Index completion was not confirmed")
        ids = [str(d["id"]) for d in result.get("documents", []) if d.get("id") is not None]
        if not ids:
            raise AccessDenied(503, "Index completion has no document receipt")
        return ids

    async def search(self, namespace, query, limit):
        try:
            result = await self.request("POST", "/api/v1/workspace/" + quote(namespace, safe="") + "/vector-search",
                                        {"query": query, "topN": limit, "scoreThreshold": 0})
        except IndexRejected:
            raise AccessDenied(502, "Index search was rejected") from None
        rows = result.get("results", [])
        for row in rows:
            text = row.get("text")
            # AnythingLLM's embedding envelope is transport metadata, not source prose.
            if isinstance(text, str) and text.startswith("passage: <document_metadata>"):
                _, separator, content = text.partition("</document_metadata>")
                if separator:
                    row["text"] = content.lstrip()
        return rows


PROVIDERS = {"anythingllm": AnythingLLM}
