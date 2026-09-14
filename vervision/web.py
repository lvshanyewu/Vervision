from __future__ import annotations

import errno
import json
import mimetypes
import os
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import __version__
from .core import _load_registry, discover_projects, module_status
from .formats import parse_document


STATIC = Path(__file__).with_name("static")


def browse_root(project: str) -> Path:
    """Open an existing handoff folder without initializing or registering it."""
    root = Path(_load_registry().get(project, project) if project else Path.cwd()).expanduser().resolve()
    if root.name == ".handoff":
        root = root.parent
    if not (root / ".handoff").is_dir():
        raise FileNotFoundError("此文件夹没有 .handoff 交接目录。请选择已有交接文件的项目；浏览器不会创建或修改文件。")
    return root


def markdown_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if root not in path.parents or path.suffix.lower() != ".md" or not path.is_file():
        raise FileNotFoundError("找不到项目内的 Markdown 文件。")
    return path


def document_json(root: Path, path: Path, full: bool = False) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    try:
        doc = parse_document(path)
        result = {**doc.meta, "revision": doc.revision}
        if full:
            result["body"] = doc.body
            if doc.meta.get("type") == "module":
                try:
                    result["freshness"] = module_status(root, doc)
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    result["notice"] = f"正文可读，来源状态暂不可用：{exc}"
    except ValueError:
        text = path.read_text(encoding="utf-8-sig")
        result = {"title": path.stem, "type": "document", "summary": "Markdown 文档"}
        if full:
            result["body"] = text
    result.update({"path": relative, "archived": "archive" in path.relative_to(root / ".handoff").parts
                   if root / ".handoff" in path.parents else False})
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
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if parsed.path == "/api/health":
                return self._json({"service": "vervision", "version": __version__, "read_only": True})
            if parsed.path == "/api/projects":
                return self._json(discover_projects())
            if parsed.path == "/api/documents":
                root = browse_root(query.get("project", [""])[0])
                documents = []
                warnings = []
                for candidate in sorted((root / ".handoff").rglob("*.md")):
                    try:
                        path = markdown_path(root, candidate.relative_to(root).as_posix())
                        item = document_json(root, path)
                        keyword = query.get("q", [""])[0].strip().casefold()
                        if not keyword or keyword in (json.dumps(item, ensure_ascii=False) + path.read_text(encoding="utf-8-sig")).casefold():
                            documents.append(item)
                    except (OSError, ValueError) as exc:
                        warnings.append(f"{candidate.name}: {exc}")
                overview = next((d for d in documents if d["path"] == ".handoff/overview.md"), {})
                return self._json({"project": str(root), "title": overview.get("title", root.name),
                                   "documents": documents, "warnings": warnings})
            if parsed.path == "/api/document":
                root = browse_root(query.get("project", [""])[0])
                path = markdown_path(root, query.get("path", [""])[0])
                return self._json(document_json(root, path, full=True))
            if parsed.path.startswith("/api/"):
                return self._json({"error": "接口不存在。"}, 404)
            name = "index.html" if parsed.path in ("", "/") else parsed.path.lstrip("/")
            target = (STATIC / name).resolve()
            if STATIC.resolve() not in target.parents or not target.is_file():
                return self.send_error(404)
            data = target.read_bytes()
            self.send_response(200)
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)
        except (OSError, ValueError, KeyError) as exc:
            self._json({"error": str(exc)}, 404)

    def do_POST(self) -> None:
        self._json({"error": "WebUI 仅供阅读，不提供编辑、初始化或核验写入。"}, 405)

    do_DELETE = do_POST
    do_PUT = do_POST
    do_PATCH = do_POST


class ReaderServer(ThreadingHTTPServer):
    # HTTPServer enables SO_REUSEADDR, which can share an occupied port on Windows.
    allow_reuse_address = False


def create_server(host: str, port: int) -> ThreadingHTTPServer:
    try:
        return ReaderServer((host, port), Handler)
    except OSError as exc:
        if not port or (exc.errno not in (errno.EACCES, errno.EADDRINUSE)
                        and getattr(exc, "winerror", None) not in (10013, 10048)):
            raise
        print(f"Port {port} is unavailable ({exc}); selecting an available port.", flush=True)
        return ReaderServer((host, 0), Handler)


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True,
          ready_file: Path | None = None) -> None:
    server = create_server(host, port)
    url = f"http://{host}:{server.server_port}/"
    try:
        if ready_file:
            ready_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = ready_file.with_suffix(f".{os.getpid()}.tmp")
            try:
                temporary.write_text(json.dumps({"service": "vervision", "version": __version__,
                                                 "url": url, "pid": os.getpid()}), encoding="utf-8")
                temporary.replace(ready_file)
            finally:
                temporary.unlink(missing_ok=True)
        print(f"Vervision {__version__} is running at {url}", flush=True)
        if open_browser:
            webbrowser.open(url)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
