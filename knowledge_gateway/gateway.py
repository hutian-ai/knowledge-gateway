from __future__ import annotations
import asyncio
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from .policy import AccessDenied
from .providers import PROVIDERS, IndexRejected
from .admin import atomic_json


class ImportDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    title: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=200000)
    previousId: UUID | None = None


class Document(ImportDocument):
    createdAt: str
    status: Literal["indexing", "ready", "unknown", "failed"]
    upstreamIds: list[str] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)
    contentSha256: str | None = None
    errorCode: str | None = None


class Search(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=50)


class Gateway:
    def __init__(self, store):
        self.store = store
        self.locks: dict[str, asyncio.Lock] = {}
        self.active: set[tuple[str, str]] = set()

    def binding(self, token, resource_id, permission):
        _, resource = self.store.authorize(token, resource_id, permission)
        base = Path(os.environ.get("KNOWLEDGE_STATE", "/run/knowledge-state"))
        directory = Path(resource.library) if resource.library else base / "libraries" / resource.namespace
        return resource, directory

    def provider(self, resource):
        try:
            connections = json.loads(Path(os.environ["KNOWLEDGE_CONNECTIONS_FILE"]).read_text())
            config = connections[resource.connection_id]
            return PROVIDERS[config["type"]](config)
        except Exception:
            raise AccessDenied(503, "Knowledge index connection is unavailable") from None

    def capabilities(self, token, resource_id):
        resource, _ = self.binding(token, resource_id, "read")
        return {"protocol_version": "knowledge-gateway/1", "resource_id": resource_id,
                "capabilities": {"formats": ["markdown"], "versions": True, "source": True,
                                 "search": True, "operations": "document_status", "delete": False}}

    def documents(self, token, resource_id, history=False):
        _, directory = self.binding(token, resource_id, "read")
        if not directory.exists():
            return []
        records = []
        for path in directory.glob("*.json"):
            try:
                UUID(path.stem)
            except ValueError:
                continue
            try:
                record = Document.model_validate_json(path.read_text()).model_dump(mode="json")
                records.append(self.observed(resource_id, record))
            except (OSError, ValueError):
                raise AccessDenied(503, "A stored document cannot be read; original file was preserved") from None
        records.sort(key=lambda d: d["createdAt"], reverse=True)
        replaced = {d["previousId"] for d in records if d["status"] == "ready" and d.get("previousId")}
        return records if history else [d for d in records if d["id"] not in replaced]

    def document(self, token, resource_id, document_id):
        _, directory = self.binding(token, resource_id, "read")
        try:
            value = Document.model_validate_json((directory / (str(UUID(document_id)) + ".json")).read_text())
        except FileNotFoundError:
            raise AccessDenied(404, "Document does not exist in this resource") from None
        except (ValueError, OSError):
            raise AccessDenied(503, "Stored document is unavailable") from None
        return self.observed(resource_id, value.model_dump(mode="json"))

    def observed(self, resource_id, value):
        if value["status"] == "indexing" and (resource_id, value["id"]) not in self.active:
            return {**value, "status": "unknown", "errorCode": "index_interrupted"}
        return value

    async def ingest(self, token, resource_id, value):
        async with self.locks.setdefault(resource_id, asyncio.Lock()):
            resource, directory = self.binding(token, resource_id, "write")
            provider = self.provider(resource)
            payload = value.model_dump(mode="json")
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            file = directory / (payload["id"] + ".json")
            if file.exists():
                old = self.document(token, resource_id, payload["id"])
                if any(old.get(k) != payload.get(k) for k in ("id", "title", "content", "previousId")):
                    raise AccessDenied(409, "Document ID already belongs to different input")
                return old  # Unknown is observable, never replayed as a new index mutation.
            records = self.documents(token, resource_id, history=True)
            pending_versions = [d for d in records if payload.get("previousId") and d.get("previousId") == payload["previousId"] and d["status"] in ("ready", "indexing", "unknown")]
            if pending_versions:
                raise AccessDenied(409, "Previous version already has a successor; inspect that document")
            prior = next((d for d in records if d["id"] == payload.get("previousId")), None)
            if payload.get("previousId") and not prior:
                raise AccessDenied(409, "Previous version is outside this resource")
            document = {**payload, "createdAt": datetime.now(timezone.utc).isoformat(), "status": "indexing",
                        "version": prior["version"] + 1 if prior else 1,
                        "contentSha256": hashlib.sha256(value.content.encode()).hexdigest(), "upstreamIds": []}
            atomic_json(file, document)
            self.active.add((resource_id, payload["id"]))
            try:
                document["upstreamIds"] = await provider.index(resource.namespace, document, resource.source_prefix + payload["id"])
                document["status"] = "ready"
            except IndexRejected:
                document.update(status="failed", errorCode="index_rejected")
            except Exception:
                document.update(status="unknown", errorCode="index_unconfirmed")
            finally:
                self.active.discard((resource_id, payload["id"]))
            atomic_json(file, document)
            return Document.model_validate(document).model_dump(mode="json")

    async def search(self, token, resource_id, value):
        resource, _ = self.binding(token, resource_id, "read")
        docs = [d for d in self.documents(token, resource_id) if d["status"] == "ready"]
        if not docs:
            return {"items": []}
        rows = await self.provider(resource).search(resource.namespace, value.query, value.limit)
        items = []
        for row in rows:
            metadata = row.get("metadata") or {}
            doc = next((d for d in docs if metadata.get("docSource") == resource.source_prefix + d["id"] or
                        metadata.get("title") == d["id"] + ".md" or str(metadata.get("id")) in d.get("upstreamIds", [])), None)
            if doc and isinstance(row.get("text"), str):
                items.append({"document_id": doc["id"], "title": doc["title"], "text": row["text"], "version": doc["version"],
                              "source_uri": resource.source_prefix + doc["id"], "score": row.get("score")})
        return {"items": items}
