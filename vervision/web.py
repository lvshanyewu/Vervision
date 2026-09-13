from __future__ import annotations

import json
import mimetypes
import time
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import __version__
from .core import (
    _load_registry, archive_module, continuation_documents, get_module, import_bundle,
    module_documents, module_status, rebuild_index, resolve_project, resolve_task,
    save_continuation, save_module, search, source_inventory, validate_project, verify_module,
)
from .formats import parse_document


STATIC = Path(__file__).with_name("static")
STATUS_CACHE: dict[tuple[str, str], tuple[float, str, dict[str, Any]]] = {}
CACHE_SECONDS = 30


def _module_json(
    root: Path, module_id: str, full: bool = True, inventory: list[Path] | None = None,
) -> dict[str, Any]:
    doc = get_module(root, module_id)
    key = (str(root), module_id)
    cached = STATUS_CACHE.get(key)
    if inventory is not None:
        status = module_status(root, doc, inventory)
        STATUS_CACHE[key] = (time.monotonic(), doc.revision, status)
    elif cached and cached[1] == doc.revision and time.monotonic() - cached[0] < CACHE_SECONDS:
        status = cached[2]
    else:
        status = module_status(root, doc)
        STATUS_CACHE[key] = (time.monotonic(), doc.revision, status)
    result = {**doc.meta, "freshness": status, "revision": doc.revision,
              "path": str(doc.path)}
    if full:
        result["body"] = doc.body
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = f"Vervision/{__version__}"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _json(self, value: Any, status: int = 200) -> None:
        data = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _error(self, exc: Exception, status: int = 400) -> None:
        self._json({"error": str(exc)}, status)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}

    def _root(self, query: dict[str, list[str]], body: dict[str, Any] | None = None) -> Path:
        project = (body or {}).get("project") or query.get("project", [None])[0]
        return resolve_project(project)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/api/projects":
            return self._json([{"id": key, "path": value} for key, value in _load_registry().items()])
        if parsed.path == "/api/modules":
            try:
                root = self._root(query)
                documents = module_documents(root)
                patterns = [pattern for doc in documents for pattern in doc.meta.get("sources", [])]
                inventory = source_inventory(root, patterns)
                modules = [_module_json(root, str(d.meta["id"]), False, inventory) for d in documents]
                return self._json({"project": str(root), "modules": modules,
                                   "continuations": len([d for d in continuation_documents(root) if d.meta.get("status") != "done"])})
            except Exception as exc:
                return self._error(exc, 404)
        if parsed.path == "/api/overview":
            try:
                root = self._root(query)
                doc = parse_document(root / ".handoff" / "overview.md")
                return self._json({**doc.meta, "body": doc.body, "revision": doc.revision, "path": str(doc.path)})
            except Exception as exc:
                return self._error(exc, 404)
        if parsed.path.startswith("/api/modules/"):
            try:
                root = self._root(query)
                module_id = urllib.parse.unquote(parsed.path.rsplit("/", 1)[-1])
                data = _module_json(root, module_id)
                data["continuations"] = [
                    {**d.meta, "body": d.body, "revision": d.revision}
                    for d in continuation_documents(root) if d.meta.get("module_id") == module_id
                ]
                return self._json(data)
            except Exception as exc:
                return self._error(exc, 404)
        if parsed.path == "/api/search":
            try:
                root = self._root(query)
                return self._json(search(root, query.get("q", [""])[0]))
            except Exception as exc:
                return self._error(exc, 404)
        if parsed.path == "/api/validate":
            try:
                root = self._root(query)
                errors = validate_project(root)
                return self._json({"valid": not errors, "errors": errors})
            except Exception as exc:
                return self._error(exc, 404)
        name = "index.html" if parsed.path in ("", "/") else parsed.path.lstrip("/")
        target = (STATIC / name).resolve()
        if STATIC.resolve() not in target.parents and target != STATIC.resolve():
            return self.send_error(HTTPStatus.NOT_FOUND)
        if not target.is_file():
            return self.send_error(HTTPStatus.NOT_FOUND)
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        try:
            body = self._body()
            root = self._root(query, body)
            if parsed.path == "/api/modules":
                return self._json(save_module(root, body, body.get("expected_revision")), 201)
            if parsed.path.endswith("/verify") and parsed.path.startswith("/api/modules/"):
                module_id = urllib.parse.unquote(parsed.path.split("/")[-2])
                result = verify_module(root, module_id, body.get("expected_revision"))
                STATUS_CACHE.pop((str(root), module_id), None)
                return self._json(result)
            if parsed.path == "/api/continuations":
                return self._json(save_continuation(root, body), 201)
            if parsed.path == "/api/resolve":
                return self._json(resolve_task(root, str(body.get("task", "")),
                                               detail=str(body.get("detail", "concise"))))
            if parsed.path == "/api/import":
                return self._json(import_bundle(root, Path(str(body["path"])), bool(body.get("replace"))))
            if parsed.path == "/api/reindex":
                return self._json(rebuild_index(root))
            return self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            return self._error(exc)

    def do_DELETE(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        try:
            root = self._root(query)
            if parsed.path.startswith("/api/modules/"):
                module_id = urllib.parse.unquote(parsed.path.rsplit("/", 1)[-1])
                expected = self.headers.get("If-Match")
                return self._json(archive_module(root, module_id, expected))
            return self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            return self._error(exc)


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"Vervision is running at {url}")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
