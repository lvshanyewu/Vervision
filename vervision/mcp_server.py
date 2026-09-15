from __future__ import annotations

import json
import sys
import secrets
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from . import __version__
from .formats import markdown_headings, read_sections
from .core import (
    continuation_documents, get_document, get_module, module_status, resolve_task,
    save_continuation, save_module, search, select_project, verify_module,
    patch_module, save_and_verify, RevisionConflict, search_page,
)


WORKSPACE_ROOTS: list[Path] = []
ROOTS_REQUEST_ID = "vervision-roots-1"
SCOPES: dict[str, Path] = {}


def _workspace_properties() -> dict[str, Any]:
    return {
        "scope_id": {"type": "string", "description": "Session project scope returned by resolve; invalid after server restart."},
        "full": {"type": "boolean", "default": False, "description": "Include body and diagnostic detail."},
        "project": {"type": "string", "description": "Optional registered project id or path."},
        "workspace": {"type": "string", "description": "Current workspace path when the MCP client does not expose roots."},
    }


TOOLS = [
    {"name": "resolve", "description": "Start here. Locate the correct project and return minimal relevant context, freshness, sources, constraints, dependencies and exact next calls.",
     "inputSchema": {"type": "object", "properties": {"task": {"type": "string"}, "detail": {"type": "string", "enum": ["concise", "detailed"], "default": "concise"}, **_workspace_properties()}, "required": ["task"]}},
    {"name": "search", "description": "Find current knowledge and open progress; default five results, has_more indicates more matches. include_history=true includes done continuations and historical body text. Exact paths rank first; next_action selects a matching unique section when available. Narrow the query or increase limit to expand.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5}, "include_history": {"type": "boolean", "default": False}, **_workspace_properties()}, "required": ["query"]}},
    {"name": "handoff_get", "description": "Unified reader for overview, module and continuation documents returned by resolve/search.",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "type": {"type": "string", "enum": ["overview", "module", "continuation"]}, "full": {"type": "boolean"}, **_workspace_properties()}, "required": ["id"]}},
    {"name": "module_status", "description": "Check source freshness and change_summary counts. changed_sources lists added/modified/removed paths since verification; null means unknown baseline. review=true adds at most five candidate sections mentioning changed paths in this module, with uncertainty. No semantic judgment or baseline diff; source-set changes may reflect sources configuration.",
     "inputSchema": {"type": "object", "properties": {"module_id": {"type": "string"}, "review": {"type": "boolean", "default": False}, **_workspace_properties()}, "required": ["module_id"]}},
    {"name": "module_save", "description": "Create or partially update a module. Existing modules require expected_revision; omitted fields are preserved and explicit empty arrays clear fields.",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "title": {"type": "string"}, "summary": {"type": "string"}, "aliases": {"type": "array", "items": {"type": "string"}}, "tags": {"type": "array", "items": {"type": "string"}}, "sources": {"type": "array", "items": {"type": "string"}}, "dependencies": {"type": "array", "items": {"type": "string"}}, "related_modules": {"type": "array", "items": {"type": "string"}}, "business_rules": {"type": "array", "items": {"type": "string"}}, "invariants": {"type": "array", "items": {"type": "string"}}, "consumers": {"type": "array", "items": {"type": "string"}}, "body": {"type": "string"}, "expected_revision": {"type": "string"}, **_workspace_properties()}, "required": ["id"]}},
    {"name": "module_verify", "description": "Record a FRESH baseline only after comparing the handoff's meaning with current source.",
     "inputSchema": {"type": "object", "properties": {"module_id": {"type": "string"}, "expected_revision": {"type": "string"}, **_workspace_properties()}, "required": ["module_id"]}},
    {"name": "continuation_save", "description": "Create or partially update temporary progress under a write lock. Omitted fields are preserved; supplied fields replace current values without a prior read. Optional expected_revision guards changes based on a read version; use 'new' for create-only. A mismatch returns the current revision; inspect affected content before retrying. Creation needs module_id and nonempty next_step; title defaults to id and status to open.",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "title": {"type": "string"}, "module_id": {"type": "string"}, "status": {"type": "string", "enum": ["open", "blocked", "done"]}, "next_step": {"type": "string"}, "body": {"type": "string"}, **_workspace_properties()}, "required": ["id", "title", "module_id", "status", "next_step"]}},
]

# Derive schemas from the same source to keep aliases and batch contracts aligned.
for kind in ("module", "overview", "continuation"):
    TOOLS.append({"name": f"{kind}_get", "description": f"Read a {kind}; full=true includes body.",
                  "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, **_workspace_properties()}, "required": ["id"]}})
_fields = dict(next(t for t in TOOLS if t["name"] == "module_save")["inputSchema"]["properties"])
for key in _workspace_properties():
    _fields.pop(key, None)
_patch = {"fields": {"type": "object", "properties": {k: v for k, v in _fields.items() if k not in ("id", "body", "expected_revision")}, "additionalProperties": False},
          "sections": {"type": "array", "items": {"type": "object", "properties": {"heading": {"type": "string"}, "body": {"type": "string"}}, "required": ["heading", "body"], "additionalProperties": False}}}
_change = {"type": "object", "properties": {**_fields, **_patch, "verify": {"type": "boolean", "default": False}}, "required": ["id"], "additionalProperties": False}
TOOLS.extend([
    {"name": "module_get_many", "description": "Read selected modules in one call; full=true includes bodies.", "inputSchema": {"type": "object", "properties": {"ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 50}, **_workspace_properties()}, "required": ["ids"]}},
    {"name": "module_patch", "description": "Patch metadata fields or uniquely named Markdown heading contents. Requires expected_revision; surrounding sections are preserved.", "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "expected_revision": {"type": "string"}, **_patch, **_workspace_properties()}, "required": ["id", "expected_revision"]}},
    {"name": "module_save_many", "description": "Save/patch up to 50 modules; explicit partial success, no batch rollback. verify=true attests Agent semantic review per item. Returns final revisions.", "inputSchema": {"type": "object", "properties": {"changes": {"type": "array", "items": _change, "minItems": 1, "maxItems": 50}, **_workspace_properties()}, "required": ["changes"]}},
    {"name": "module_save_and_verify", "description": "Save/patch and attest completed semantic review in one call. Save remains if verification fails; final revision always returned.", "inputSchema": {"type": "object", "properties": {**_change["properties"], **_workspace_properties()}, "required": ["id"]}},
])
_continuation = next(t for t in TOOLS if t["name"] == "continuation_save")["inputSchema"]
_continuation["required"] = ["id"]
_continuation["properties"].update({"expected_revision": {"type": "string"}, "external_checks": {"type": "array", "items": {"type": "object", "properties": {"service": {"type": "string"}, "status": {"type": "string"}, "evidence": {"type": "string"}, "checked_at": {"type": "string"}}, "required": ["service", "status", "evidence", "checked_at"], "additionalProperties": False}}})

for tool in TOOLS:
    if tool["name"] in ("handoff_get", "module_get", "overview_get", "continuation_get", "module_get_many"):
        tool["description"] += " Default returns metadata and section headings. sections reads selected unique ATX headings (including children); full=true reads the whole document. Linked continuation bodies require continuation_get."
        tool["inputSchema"]["properties"]["sections"] = {
            "type": "array", "items": {"type": "string"}, "minItems": 1,
            "description": "Exact unique ATX heading names; cannot combine with full=true. Batch applies the same selection to each module and reports per-module errors."}


def _workspaces(args: dict[str, Any]) -> list[Path]:
    if args.get("workspace"):
        return [Path(str(args["workspace"]))]
    return list(WORKSPACE_ROOTS)


def _selection(args: dict[str, Any], *, task: str = "", document_id: str | None = None) -> dict[str, Any]:
    if args.get("scope_id"):
        root = SCOPES.get(str(args["scope_id"]))
        if root is None or not (root / ".handoff" / "overview.md").is_file():
            raise ValueError("Unknown or expired scope_id; call resolve again with explicit project/workspace.")
        if args.get("project"):
            selected = select_project(project=args["project"])
            if Path(selected["selected"]).resolve() != root:
                raise ValueError("scope_id conflicts with project")
        if args.get("workspace"):
            workspace = Path(args["workspace"]).resolve()
            if workspace != root and root not in workspace.parents:
                raise ValueError("scope_id conflicts with workspace")
        return {"selected": str(root), "status": "selected", "reason": "session scope", "candidates": []}
    return select_project(task=task, project=args.get("project"), workspaces=_workspaces(args) or None,
                          document_id=document_id)


def _root_or_error(args: dict[str, Any], *, task: str = "", document_id: str | None = None) -> tuple[Path, dict[str, Any]]:
    selection = _selection(args, task=task, document_id=document_id)
    if not selection.get("selected"):
        choices = [{"project": c["id"], "path": c["path"], "score": c["score"]} for c in selection["candidates"]]
        raise FileNotFoundError(f"{selection['reason']} Retry with project set to one candidate: {json.dumps(choices, ensure_ascii=False)}")
    return Path(selection["selected"]), selection


def _call_tool(name: str, args: dict[str, Any]) -> Any:
    if args.get("sections") and args.get("full") and name in (
            "handoff_get", "module_get", "overview_get", "continuation_get", "module_get_many"):
        raise ValueError("Use sections or full=true, not both")
    if name == "resolve":
        selection = _selection(args, task=str(args["task"]))
        if not selection.get("selected"):
            return {"task": args["task"], "project_selection": selection,
                    "next_actions": [{"tool": "resolve", "arguments": {"task": args["task"], "project": c["path"]}}
                                     for c in selection["candidates"]]}
        detail = "detailed" if args.get("full") else str(args.get("detail", "concise"))
        result = resolve_task(Path(selection["selected"]), str(args["task"]), detail=detail)
        root = Path(selection["selected"]).resolve()
        scope = next((key for key, value in SCOPES.items() if value == root), None)
        if scope is None:
            scope = secrets.token_urlsafe(18)
            SCOPES[scope] = root
        result["scope_id"] = scope
        for action in result["next_actions"]:
            action["arguments"].pop("project", None)
            action["arguments"]["scope_id"] = scope
        if detail == "detailed" or args.get("full"):
            result["project_selection"] = selection
        return result
    if name == "search":
        root, selection = _root_or_error(args, task=str(args["query"]))
        return {"project_selection": selection, **search_page(root, str(args["query"]), args.get("limit", 5), args.get("include_history", False))}
    if name == "module_get_many":
        root, _ = _root_or_error(args)
        ids = args["ids"]
        if not isinstance(ids, list) or not 1 <= len(ids) <= 50:
            raise ValueError("ids must contain 1..50 module ids")
        results = []
        for document_id in ids:
            try:
                value = call_tool("module_get", {"project": str(root), "id": document_id,
                                  **{k: args[k] for k in ("full", "sections") if k in args}})
                value.pop("project_selection", None)
                results.append(value)
            except Exception as exc:
                results.append({"id": document_id, "error": str(exc)})
        return {"results": results}
    if name in ("handoff_get", "module_get", "overview_get", "continuation_get"):
        document_id = str(args.get("id") or args.get("module_id"))
        root, selection = _root_or_error(args, document_id=document_id)
        doc = get_document(root, document_id, args.get("type") or (name.removesuffix("_get") if name != "handoff_get" else None))
        value = {**doc.meta, "revision": doc.revision, "path": str(doc.path), "project_selection": selection}
        value["sections"] = [heading for _, _, heading in markdown_headings(doc.body)]
        if doc.meta.get("type") == "module":
            value["freshness"] = module_status(root, doc)
            value["continuations"] = [{k: d.meta.get(k) for k in ("id", "title", "status")}
                                      for d in continuation_documents(root)
                                      if d.meta.get("module_id") == doc.meta.get("id")
                                      and (args.get("full") or d.meta.get("status") != "done")]
        if args.get("full", False):
            value["body"] = doc.body
        elif args.get("sections"):
            value["body"] = read_sections(doc.body, args["sections"])
        return value
    document_id = str(args.get("module_id") or args.get("id") or "")
    root, _ = _root_or_error(args, document_id=document_id or None)
    if name == "module_status":
        return module_status(root, get_module(root, str(args["module_id"])), review=args.get("review", False))
    if name == "module_save":
        return save_and_verify(root, args)
    if name == "module_patch":
        return save_and_verify(root, args)
    if name == "module_save_and_verify":
        return save_and_verify(root, {**args, "verify": True})
    if name == "module_save_many":
        changes = args["changes"]
        if not isinstance(changes, list) or not 1 <= len(changes) <= 50:
            raise ValueError("changes must contain 1..50 items")
        ids = [item["id"] for item in changes]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate module ids in batch")
        if any(set(item) & set(_workspace_properties()) for item in changes):
            raise ValueError("Project scope belongs on the batch, not individual changes")
        results = []
        for change in changes:
            try:
                results.append({"ok": True, **save_and_verify(root, change)})
            except Exception as exc:
                results.append({"id": change.get("id"), "ok": False, "changed": False,
                                "error": getattr(exc, "details", {"message": str(exc)})})
        return {"mode": "partial", "results": results,
                "ok": all(r["ok"] and not r.get("verification_error") for r in results)}
    if name == "module_verify":
        return verify_module(root, str(args["module_id"]), args.get("expected_revision"))
    if name == "continuation_save":
        return save_continuation(root, args)
    raise KeyError(f"Unknown tool '{name}'")


def call_tool(name: str, args: dict[str, Any]) -> Any:
    if name not in {t["name"] for t in TOOLS}:
        raise KeyError(f"Unknown tool '{name}'")
    schema = next(t["inputSchema"] for t in TOOLS if t["name"] == name)
    _validate(args, schema)
    result = _call_tool(name, args)
    if args.get("full") or args.get("detail") == "detailed":
        return result
    if name == "resolve":
        for item in result.get("matches", []):
            item["match_reason"].pop("snippet", None)
            item.pop("source_patterns", None)
            item.pop("consumers", None)
            item["freshness"] = {"source_freshness": item["freshness"]["state"],
                                 "document_verification": item["freshness"]["document_verification"]["state"],
                                 "external_checks": "NOT_CHECKED"}
        if result.get("project_context", {}).get("architecture") == result.get("project_context", {}).get("summary"):
            result["project_context"].pop("architecture", None)
        return result
    if name.endswith("_get"):
        if "freshness" in result:
            result["source_freshness"] = result["freshness"]["state"]
            result["document_verification"] = result["freshness"]["document_verification"]["state"]
            result["external_checks"] = "NOT_CHECKED"
        return {k: v for k, v in result.items() if k in ("id", "type", "title", "summary", "revision", "status", "next_step", "module_id", "external_checks", "source_freshness", "document_verification", "sections", "sources", "continuations", "body", "path")}
    if name == "module_save_many":
        result["results"] = [_compact_write(item) for item in result["results"]]
    if name in ("module_save", "module_patch", "module_verify", "module_save_and_verify", "continuation_save"):
        return _compact_write(result)
    result.pop("project_selection", None)
    result.pop("path", None)
    return result


def _compact_write(value):
    return {k: v for k, v in value.items() if k in (
        "id", "module_id", "revision", "changed", "verified", "verification_changed", "status", "state",
        "ok", "error", "verification_error", "warnings")}


def _validate(value, schema, path="arguments"):
    expected = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "boolean": bool, "integer": int}
    if expected in types and not isinstance(value, types[expected]):
        raise ValueError(f"{path} must be {expected}")
    if expected == "integer" and (isinstance(value, bool) or not schema.get("minimum", -float("inf")) <= value <= schema.get("maximum", float("inf"))):
        raise ValueError(f"{path} is outside the allowed integer range")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path} must be one of {schema['enum']}")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        missing = set(schema.get("required", [])) - value.keys()
        if missing:
            raise ValueError(f"{path} missing: {', '.join(sorted(missing))}")
        unknown = value.keys() - properties.keys()
        if unknown and schema.get("additionalProperties") is False:
            raise ValueError(f"{path} unknown fields: {', '.join(sorted(unknown))}")
        for key in value.keys() & properties.keys():
            _validate(value[key], properties[key], f"{path}.{key}")
    elif isinstance(value, list):
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", float("inf")):
            raise ValueError(f"{path} has invalid item count")
        for item in value:
            _validate(item, schema.get("items", {}), f"{path}[]")


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
                SCOPES.clear()
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
                    _response(request_id, {"structuredContent": result, "content": [{"type": "text", "text": "Vervision result is in structuredContent."}], "isError": False})
                except Exception as exc:
                    _response(request_id, {"structuredContent": {"error": getattr(exc, "details", {"message": str(exc)})}, "content": [{"type": "text", "text": str(exc)}], "isError": True})
            elif method == "ping":
                _response(request_id, {})
            elif request_id is not None and not str(method).startswith("notifications/"):
                _response(request_id, error={"code": -32601, "message": f"Method not found: {method}"})
        except Exception as exc:
            _response(None, error={"code": -32700, "message": str(exc)})
