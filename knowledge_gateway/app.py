from __future__ import annotations
import os
from contextlib import asynccontextmanager
from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID
from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from mcp.server.fastmcp import FastMCP
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from .policy import PolicyStore, AccessDenied
from .gateway import Gateway, ImportDocument, Document, Search
from .management import mount_management

store = PolicyStore(os.environ.get("KNOWLEDGE_POLICY", "/run/knowledge/policy.json"))
gateway = Gateway(store)
public_url = os.environ.get("KNOWLEDGE_PUBLIC_URL", "http://127.0.0.1:3333").rstrip("/")
bearer = HTTPBearer(auto_error=False)


class Verifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        credential = store.authenticate(token)
        if credential is None:
            return None
        return AccessToken(token=token, client_id=credential.id, scopes=["knowledge"],
                           expires_at=credential.expires_at, resource=public_url + "/mcp")


mcp = FastMCP("Knowledge Gateway", stateless_http=True, json_response=True, streamable_http_path="/",
    token_verifier=Verifier(), auth=AuthSettings(issuer_url=public_url, resource_server_url=public_url + "/mcp",
                                                required_scopes=["knowledge"], validate_token_resource=True),
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", urlsplit(public_url).netloc], allowed_origins=[public_url]),
    instructions="Use only authorized resources. Preserve document IDs and immutable version references. Unknown imports must be observed by their original ID, never blindly retried with a new ID.")


@asynccontextmanager
async def lifespan(app):
    store.load()
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="Knowledge Gateway", version="0.1.0", lifespan=lifespan)


@app.exception_handler(AccessDenied)
async def access_error(request: Request, error: AccessDenied):
    return JSONResponse({"detail": error.message}, status_code=error.status,
                        headers={"WWW-Authenticate": "Bearer"} if error.status == 401 else {})


def token(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    if credentials is None or store.authenticate(credentials.credentials) is None:
        raise AccessDenied(401, "Credential is invalid, expired or revoked")
    return credentials.credentials


def mcp_token():
    value = get_access_token()
    if value is None or store.authenticate(value.token) is None:
        raise ValueError("Credential is invalid, expired or revoked")
    return value.token


@app.get("/health")
def health():
    store.load()
    return {"status": "ok", "protocol": "knowledge-gateway/1"}


@app.get("/v1/resources")
def resources(raw_token: str = Depends(token)):
    credential = store.authenticate(raw_token)
    if credential is None:
        raise AccessDenied(401, "Invalid credential")
    return {"resources": [gateway.capabilities(raw_token, key) for key, grants in credential.grants.items() if "read" in grants]}


@app.get("/v1/resources/{resource_id}/capabilities")
def capabilities(resource_id: str, raw_token: str = Depends(token)):
    return gateway.capabilities(raw_token, resource_id)


@app.get("/v1/resources/{resource_id}/documents", response_model=list[Document])
def documents(resource_id: str, history: bool = False, raw_token: str = Depends(token)):
    return gateway.documents(raw_token, resource_id, history)


@app.get("/v1/resources/{resource_id}/documents/{document_id}", response_model=Document)
def document(resource_id: str, document_id: UUID, raw_token: str = Depends(token)):
    return gateway.document(raw_token, resource_id, str(document_id))


@app.post("/v1/resources/{resource_id}/documents", response_model=Document)
async def ingest(resource_id: str, value: ImportDocument, raw_token: str = Depends(token)):
    return await gateway.ingest(raw_token, resource_id, value)


@app.post("/v1/resources/{resource_id}/search")
async def search(resource_id: str, value: Search, raw_token: str = Depends(token)):
    return await gateway.search(raw_token, resource_id, value)


@app.get("/v1/resources/{resource_id}/operations/{document_id}")
def operation(resource_id: str, document_id: UUID, raw_token: str = Depends(token)):
    doc = gateway.document(raw_token, resource_id, str(document_id))
    return {"operation_id": doc["id"], "document_id": doc["id"], "version": doc["version"],
            "status": {"ready": "completed", "indexing": "processing"}.get(doc["status"], doc["status"]),
            "error_code": doc.get("errorCode")}


@mcp.tool()
def knowledge_resources() -> dict:
    """Discover only the knowledge resources granted to this client."""
    return resources(mcp_token())


@mcp.tool()
def knowledge_capabilities(resource_id: str) -> dict:
    """Discover supported formats and operations."""
    return gateway.capabilities(mcp_token(), resource_id)


@mcp.tool()
async def knowledge_import(resource_id: str, document_id: UUID, title: str, content: str, previous_id: UUID | None = None) -> dict:
    """Import Markdown under a stable document ID; a new version names its predecessor."""
    return await gateway.ingest(mcp_token(), resource_id, ImportDocument(id=document_id, title=title, content=content, previousId=previous_id))


@mcp.tool()
def knowledge_source(resource_id: str, document_id: UUID) -> dict:
    """Read the original text and version referenced by a retrieval result."""
    return gateway.document(mcp_token(), resource_id, str(document_id))


@mcp.tool()
async def knowledge_search(resource_id: str, query: str, limit: int = 5) -> dict:
    """Retrieve fragments with original document IDs and immutable versions."""
    return await gateway.search(mcp_token(), resource_id, Search(query=query, limit=limit))


@mcp.tool()
def knowledge_operation(resource_id: str, document_id: UUID) -> dict:
    """Observe the original document's indexing state without issuing another import."""
    return operation(resource_id, document_id, mcp_token())


mount_management(app, store)
app.mount("/mcp", mcp.streamable_http_app())
