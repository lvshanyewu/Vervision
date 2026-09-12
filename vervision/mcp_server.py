from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from . import __version__
from .core import (
    continuation_documents, get_document, get_module, module_status, resolve_task,
    save_continuation, save_module, search, select_project, verify_module,
)


WORKSPACE_ROOTS: list[Path] = []
ROOTS_REQUEST_ID = "vervision-roots-1"


def _workspace_properties() -> dict[str, Any]:
    return {
        "project": {"type": "string", "description": "Optional registered project id or path."},
        "workspace": {"type": "string", "description": "Current workspace path when the MCP client does not expose roots."},
    }


TOOLS = [
    {"name": "resolve", "description": "Start here. Locate the correct project and return minimal relevant context, freshness, sources, constraints, dependencies and exact next calls.",
     "inputSchema": {"type": "object", "properties": {"task": {"type": "string"}, "detail": {"type": "string", "enum": ["concise", "detailed"], "default": "concise"}, **_workspace_properties()}, "required": ["task"]}},
    {"name": "search", "description": "Search all handoff document types. Every result includes the exact handoff_get call that reads it.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, **_workspace_properties()}, "required": ["query"]}},
    {"name": "handoff_get", "description": "Unified reader for overview, module and continuation documents returned by resolve/search.",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "type": {"type": "string", "enum": ["overview", "module", "continuation"]}, "full": {"type": "boolean"}, **_workspace_properties()}, "required": ["id"]}},
    {"name": "module_status", "description": "Check source freshness and the independent handoff semantic verification state; list resolved and missing source paths.",
     "inputSchema": {"type": "object", "properties": {"module_id": {"type": "string"}, **_workspace_properties()}, "required": ["module_id"]}},
    {"name": "module_save", "description": "Create or partially update a module. Existing modules require expected_revision; omitted fields are preserved and explicit empty arrays clear fields.",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "title": {"type": "string"}, "summary": {"type": "string"}, "aliases": {"type": "array", "items": {"type": "string"}}, "tags": {"type": "array", "items": {"type": "string"}}, "sources": {"type": "array", "items": {"type": "string"}}, "dependencies": {"type": "array", "items": {"type": "string"}}, "related_modules": {"type": "array", "items": {"type": "string"}}, "business_rules": {"type": "array", "items": {"type": "string"}}, "invariants": {"type": "array", "items": {"type": "string"}}, "consumers": {"type": "array", "items": {"type": "string"}}, "body": {"type": "string"}, "expected_revision": {"type": "string"}, **_workspace_properties()}, "required": ["id"]}},
    {"name": "module_verify", "description": "Record a FRESH baseline only after comparing the handoff's meaning with current source.",
     "inputSchema": {"type": "object", "properties": {"module_id": {"type": "string"}, "expected_revision": {"type": "string"}, **_workspace_properties()}, "required": ["module_id"]}},
    {"name": "continuation_save", "description": "Record lightweight cross-session progress and one concrete next action.",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "title": {"type": "string"}, "module_id": {"type": "string"}, "status": {"type": "string", "enum": ["open", "blocked", "done"]}, "next_step": {"type": "string"}, "body": {"type": "string"}, **_workspace_properties()}, "required": ["id", "title", "module_id", "status", "next_step"]}},
]


def _workspaces(args: dict[str, Any]) -> list[Path]:
    values = list(WORKSPACE_ROOTS)
    if args.get("workspace"):
        values.insert(0, Path(str(args["workspace"])))
    return values


def _selection(args: dict[str, Any], *, task: str = "", document_id: str | None = None) -> dict[str, Any]:
    return select_project(task=task, project=args.get("project"), workspaces=_workspaces(args) or None,
                          document_id=document_id)


def _root_or_error(args: dict[str, Any], *, task: str = "", document_id: str | None = None) -> tuple[Path, dict[str, Any]]:
    selection = _selection(args, task=task, document_id=document_id)
    if not selection.get("selected"):
        choices = [{"project": c["id"], "path": c["path"], "score": c["score"]} for c in selection["candidates"]]
        raise FileNotFoundError(f"{selection['reason']} Retry with project set to one candidate: {json.dumps(choices, ensure_ascii=False)}")
    return Path(selection["selected"]), selection


def call_tool(name: str, args: dict[str, Any]) -> Any:
    if name == "resolve":
        selection = _selection(args, task=str(args["task"]))
        if not selection.get("selected"):
            return {"task": args["task"], "project_selection": selection,
                    "next_actions": [{"tool": "resolve", "arguments": {"task": args["task"], "project": c["id"]}}
                                     for c in selection["candidates"]]}
        detail = str(args.get("detail", "concise"))
        result = resolve_task(Path(selection["selected"]), str(args["task"]), detail=detail)
        if detail == "detailed" or not args.get("project"):
            result["project_selection"] = selection
        return result
    if name == "search":
        root, selection = _root_or_error(args, task=str(args["query"]))
        return {"project_selection": selection, "results": search(root, str(args["query"]))}
    if name in ("handoff_get", "module_get"):
        document_id = str(args.get("id") or args.get("module_id"))
        root, selection = _root_or_error(args, document_id=document_id)
        doc = get_document(root, document_id, args.get("type") or ("module" if name == "module_get" else None))
        value = {**doc.meta, "revision": doc.revision, "path": str(doc.path), "project_selection": selection}
        if doc.meta.get("type") == "module":
            value["freshness"] = module_status(root, doc)
            value["continuations"] = [{**d.meta, "body": d.body} for d in continuation_documents(root)
                                      if d.meta.get("module_id") == doc.meta.get("id")]
        if args.get("full", True):
            value["body"] = doc.body
        return value
    document_id = str(args.get("module_id") or args.get("id") or "")
    root, _ = _root_or_error(args, document_id=document_id or None)
    if name == "module_status":
        return module_status(root, get_module(root, str(args["module_id"])))
    if name == "module_save":
        return save_module(root, args, args.get("expected_revision"))
    if name == "module_verify":
        return verify_module(root, str(args["module_id"]), args.get("expected_revision"))
    if name == "continuation_save":
        return save_continuation(root, args)
    raise KeyError(f"Unknown tool '{name}'")


def _write(payload: dict[str, Any]) -> None:
    sys.stdout.buffer.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def _response(request_id: Any, result: Any = None, error: dict[str, Any] | None = None) -> None:
    payload = {"jsonrpc": "2.0", "id": request_id}
    payload["error" if error else "result"] = error if error else result
    _write(payload)


def _request_roots() -> None:
    _write({"jsonrpc": "2.0", "id": ROOTS_REQUEST_ID, "method": "roots/list"})


def _accept_roots(result: dict[str, Any]) -> None:
    WORKSPACE_ROOTS.clear()
    for item in result.get("roots", []):
        parsed = urllib.parse.urlparse(str(item.get("uri", "")))
        if parsed.scheme != "file":
            continue
        raw = urllib.request.url2pathname(urllib.parse.unquote(parsed.path))
        if parsed.netloc:
            raw = f"//{parsed.netloc}{raw}"
        if len(raw) >= 3 and raw[0] == "/" and raw[2] == ":":
            raw = raw[1:]
        WORKSPACE_ROOTS.append(Path(raw).resolve())


def run() -> None:
    client_supports_roots = False
    for raw_bytes in sys.stdin.buffer:
        try:
            req = json.loads(raw_bytes.decode("utf-8"))
            method = req.get("method")
            request_id = req.get("id")
            if request_id == ROOTS_REQUEST_ID and "result" in req:
                _accept_roots(dict(req["result"] or {}))
            elif method == "initialize":
                client_supports_roots = bool(req.get("params", {}).get("capabilities", {}).get("roots"))
                _response(request_id, {"protocolVersion": "2025-06-18", "capabilities": {"tools": {"listChanged": False}},
                                       "serverInfo": {"name": "vervision", "version": __version__}})
            elif method == "notifications/initialized":
                if client_supports_roots:
                    _request_roots()
            elif method == "notifications/roots/list_changed":
                if client_supports_roots:
                    _request_roots()
            elif method == "tools/list":
                _response(request_id, {"tools": TOOLS})
            elif method == "tools/call":
                params = req.get("params", {})
                try:
                    result = call_tool(str(params.get("name")), dict(params.get("arguments") or {}))
                    _response(request_id, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}], "isError": False})
                except Exception as exc:
                    _response(request_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
            elif method == "ping":
                _response(request_id, {})
            elif request_id is not None and not str(method).startswith("notifications/"):
                _response(request_id, error={"code": -32601, "message": f"Method not found: {method}"})
        except Exception as exc:
            _response(None, error={"code": -32700, "message": str(exc)})
