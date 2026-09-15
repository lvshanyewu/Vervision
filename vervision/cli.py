from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from . import __version__
from .core import (
    import_bundle, init_project, module_documents, module_status, rebuild_index,
    resolve_project, resolve_task, search_page, select_project, validate_project, verify_module,
)


def emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="handoff", description="Vervision local project handoff router")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Initialize .handoff in a project")
    init.add_argument("path", nargs="?", default=".")
    init.add_argument("--id")
    init.add_argument("--title")
    for name in ("validate", "reindex", "status"):
        item = sub.add_parser(name)
        item.add_argument("--project")
    search_p = sub.add_parser("search")
    search_p.add_argument("query")
    search_p.add_argument("--project")
    search_p.add_argument("--include-history", action="store_true", help="Include done progress and historical body text")
    search_p.add_argument("--limit", type=int, default=5, help="Result count, 1..50 (default 5)")
    resolve_p = sub.add_parser("resolve")
    resolve_p.add_argument("task")
    resolve_p.add_argument("--project")
    resolve_p.add_argument("--detail", choices=("concise", "detailed"), default="concise")
    verify = sub.add_parser("verify")
    verify.add_argument("module_id")
    verify.add_argument("--project")
    import_p = sub.add_parser("import")
    import_p.add_argument("source")
    import_p.add_argument("--project")
    import_p.add_argument("--replace", action="store_true")
    gui = sub.add_parser("gui")
    gui.add_argument("--host", default="127.0.0.1")
    gui.add_argument("--port", type=int, default=8765)
    gui.add_argument("--no-browser", action="store_true")
    gui.add_argument("--ready-file", type=Path, help="Write the actual local server URL for the launcher")
    sub.add_parser("mcp")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            handoff = init_project(Path(args.path), args.id, args.title)
            rebuild_index(handoff.parent)
            emit({"initialized": str(handoff), "next": "Edit .handoff/overview.md, add modules, then run handoff validate."})
        elif args.command == "validate":
            root = resolve_project(args.project)
            errors = validate_project(root)
            emit({"valid": not errors, "errors": errors})
            return 1 if errors else 0
        elif args.command == "reindex":
            emit(rebuild_index(resolve_project(args.project)))
        elif args.command == "status":
            root = resolve_project(args.project)
            emit({str(d.meta["id"]): module_status(root, d) for d in module_documents(root)})
        elif args.command == "search":
            selection = select_project(task=args.query, project=args.project)
            if not selection["selected"]:
                emit({"project_selection": selection, "next": "Retry with --project <candidate-id-or-path>."})
                return 2
            emit({"project_selection": selection, **search_page(Path(selection["selected"]), args.query, args.limit, args.include_history)})
        elif args.command == "resolve":
            selection = select_project(task=args.task, project=args.project)
            if not selection["selected"]:
                emit({"task": args.task, "project_selection": selection, "next": "Retry with --project <candidate-id-or-path>."})
                return 2
            result = resolve_task(Path(selection["selected"]), args.task, detail=args.detail)
            if args.detail == "detailed" or not args.project:
                result["project_selection"] = selection
            emit(result)
        elif args.command == "verify":
            emit(verify_module(resolve_project(args.project), args.module_id))
        elif args.command == "import":
            result = import_bundle(resolve_project(args.project), Path(args.source), args.replace)
            emit(result)
            return 1 if result["errors"] else 0
        elif args.command == "gui":
            from .web import serve
            serve(args.host, args.port, not args.no_browser, args.ready_file)
        elif args.command == "mcp":
            from .mcp_server import run
            run()
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
