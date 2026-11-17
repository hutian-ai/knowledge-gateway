"""Small standalone CLI using the same scoped HTTP contract as the SDK and MCP."""
import argparse
import json
from pathlib import Path
from urllib.parse import quote
import httpx


def main():
    parser = argparse.ArgumentParser(description="Use an authorized Knowledge Gateway")
    parser.add_argument("--config", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("resources")
    for name in ("capabilities", "list", "source", "operation", "search", "import"):
        child = sub.add_parser(name)
        child.add_argument("resource")
        if name in ("source", "operation", "import"):
            child.add_argument("document_id")
        if name == "list":
            child.add_argument("--history", action="store_true")
        if name == "search":
            child.add_argument("query")
        if name == "import":
            child.add_argument("--title", required=True)
            child.add_argument("--file", type=Path, required=True)
            child.add_argument("--previous-id")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    method, path, body = "GET", "/v1/resources", None
    if args.command != "resources":
        path += "/" + quote(args.resource, safe="")
        if args.command == "capabilities": path += "/capabilities"
        elif args.command == "list": path += "/documents" + ("?history=true" if args.history else "")
        elif args.command == "source": path += "/documents/" + quote(args.document_id, safe="")
        elif args.command == "operation": path += "/operations/" + quote(args.document_id, safe="")
        elif args.command == "search":
            method, path, body = "POST", path + "/search", {"query": args.query}
        elif args.command == "import":
            method, path = "POST", path + "/documents"
            body = {"id": args.document_id, "title": args.title, "content": args.file.read_text(), "previousId": args.previous_id}
    try:
        r = httpx.request(method, config["url"].rstrip("/") + path, json=body,
                          headers={"Authorization": "Bearer " + config["token"]}, timeout=45, follow_redirects=False)
        if not r.is_success:
            raise SystemExit("Gateway rejected the operation (HTTP " + str(r.status_code) + ")")
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
    except httpx.RequestError:
        raise SystemExit("Gateway response is unconfirmed; query the original document ID") from None


if __name__ == "__main__":
    main()
