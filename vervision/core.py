from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
from difflib import SequenceMatcher
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from contextlib import contextmanager

from .formats import Document, dump_document, parse_document, validate_document
from .locking import writer


APP_HOME = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local")) / "Vervision"
REGISTRY = APP_HOME / "projects.json"
INDEX = APP_HOME / "index.sqlite3"
SEMANTIC_DIGEST_EXCLUDED_FIELDS = {
    "updated_at", "verified_at", "verified_digest", "verified_document_digest",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _write_document(path: Path, meta: dict[str, Any], body: str) -> None:
    """Readers see either the previous complete document or the new one."""
    descriptor, temporary = tempfile.mkstemp(prefix=".vervision-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(dump_document(meta, body))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _load_registry() -> dict[str, str]:
    if not REGISTRY.exists():
        return {}
    try:
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_registry(data: dict[str, str]) -> None:
    APP_HOME.mkdir(parents=True, exist_ok=True)
    temp = REGISTRY.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(REGISTRY)


def _is_project(path: Path) -> bool:
    return (path / ".handoff" / "overview.md").is_file()


def _normal_path(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    return path.parent if path.is_file() else path


def discover_projects(workspaces: Iterable[str | Path] | None = None) -> list[dict[str, Any]]:
    """Find initialized projects without assuming that the process cwd is the source root."""
    starts = [_normal_path(value) for value in (workspaces or [os.getcwd()])]
    found: dict[str, dict[str, Any]] = {}

    def add(path: Path, reason: str) -> None:
        try:
            root = path.resolve()
        except OSError:
            return
        if _is_project(root):
            entry = found.setdefault(str(root).casefold(), {"root": root, "reasons": set()})
            entry["reasons"].add(reason)

    for start in starts:
        for distance, current in enumerate((start, *start.parents)):
            add(current, "workspace" if distance == 0 else f"parent:{distance}")
        # Direct siblings cover common layouts such as D:\docs beside D:\source.
        for container in (start.parent, *list(start.parents)[:1]):
            try:
                for child in container.iterdir():
                    if child.is_dir():
                        add(child, "adjacent")
            except OSError:
                continue
    registry = _load_registry()
    for project_id, raw_path in registry.items():
        add(Path(raw_path), f"registered:{project_id}")

    candidates: list[dict[str, Any]] = []
    for entry in found.values():
        root = entry["root"]
        reasons = entry["reasons"]
        try:
            overview = parse_document(root / ".handoff" / "overview.md")
        except (OSError, ValueError):
            continue
        candidates.append({
            "id": str(overview.meta.get("id", root.name)),
            "title": str(overview.meta.get("title", root.name)),
            "summary": str(overview.meta.get("summary", "")),
            "path": str(root),
            "reasons": sorted(reasons),
        })
    return sorted(candidates, key=lambda item: item["id"])


def select_project(
    task: str = "", project: str | None = None,
    workspaces: Iterable[str | Path] | None = None, document_id: str | None = None,
) -> dict[str, Any]:
    registry = _load_registry()
    if project:
        explicit = Path(registry.get(project, project)).expanduser()
        root = _normal_path(explicit)
        for current in (root, *root.parents):
            if _is_project(current):
                return {"status": "selected", "selected": str(current), "reason": "explicit project", "candidates": []}
        raise FileNotFoundError(f"Vervision project '{project}' was not found or is not initialized.")

    starts = [_normal_path(value) for value in (workspaces or [os.getcwd()])]
    candidates = discover_projects(starts)
    for item in candidates:
        root = Path(item["path"])
        score = 2 if any(r.startswith("registered:") for r in item["reasons"]) else 0
        proximity = 0
        for start in starts:
            if root == start:
                proximity = max(proximity, 25)
            elif root in start.parents:
                proximity = max(proximity, 20 - list(start.parents).index(root))
            elif root.parent == start.parent:
                proximity = max(proximity, 5 + round(5 * SequenceMatcher(None, root.name.casefold(), start.name.casefold()).ratio()))
        score += proximity
        task_results = search(root, task, limit=1, include_next=False) if task.strip() else []
        relevance = int(task_results[0]["score"]) if task_results else 0
        score += relevance * 3
        if document_id and any(str(d.meta.get("id")) == document_id for d in project_documents(root)):
            score += 50
            item["reasons"].append("contains requested document")
        item.update({"score": score, "task_relevance": relevance})

    candidates.sort(key=lambda item: (-item["score"], item["id"]))
    if not candidates:
        return {"status": "not_found", "selected": None, "reason": "No initialized project was found.", "candidates": []}
    top = candidates[0]
    anchored = {}
    for start in starts:
        containing = [c for c in candidates if Path(c["path"]) == start or Path(c["path"]) in start.parents]
        if containing:
            nearest = max(containing, key=lambda c: len(Path(c["path"]).parts))
            anchored[nearest["path"]] = nearest
    if len(anchored) == 1:
        selected = next(iter(anchored))
        return {"status": "selected", "selected": selected, "reason": "workspace containment", "candidates": candidates[:5]}
    if len(candidates) == 1:
        return {"status": "selected", "selected": top["path"], "reason": "unique clear match", "candidates": candidates[:5]}
    return {"status": "ambiguous", "selected": None,
            "reason": "Several projects are plausible; choose one by id or path.", "candidates": candidates[:5]}


def resolve_project(project: str | None = None, workspaces: Iterable[str | Path] | None = None) -> Path:
    selection = select_project(project=project, workspaces=workspaces)
    if selection["selected"]:
        return Path(selection["selected"])
    choices = ", ".join(f"{c['id']} ({c['path']})" for c in selection["candidates"])
    raise FileNotFoundError(f"{selection['reason']} Candidates: {choices}" if choices else selection["reason"])


def register_project(root: Path) -> None:
    overview = parse_document(root / ".handoff" / "overview.md")
    data = _load_registry()
    data[str(overview.meta["id"])] = str(root.resolve())
    _save_registry(data)


def init_project(root: Path, project_id: str | None = None, title: str | None = None) -> Path:
    root = root.resolve()
    handoff = root / ".handoff"
    (handoff / "modules").mkdir(parents=True, exist_ok=True)
    (handoff / "continuations").mkdir(parents=True, exist_ok=True)
    (handoff / "archive").mkdir(parents=True, exist_ok=True)
    overview = handoff / "overview.md"
    if not overview.exists():
        pid = project_id or root.name.lower().replace(" ", "-")
        meta = {
            "schema_version": 1, "type": "overview", "id": pid,
            "title": title or root.name, "summary": "Project handoff overview.",
            "aliases": [], "tags": [], "updated_at": now_iso(),
        }
        overview.write_text(dump_document(meta, "# Overview\n\nDescribe the project and link its modules here."), encoding="utf-8")
    register_project(root)
    return handoff


def project_documents(root: Path) -> list[Document]:
    docs: list[Document] = []
    for path in sorted((root / ".handoff").rglob("*.md")):
        if "archive" in path.parts:
            continue
        try:
            docs.append(parse_document(path))
        except (OSError, ValueError):
            continue
    return docs


def module_documents(root: Path) -> list[Document]:
    return [d for d in project_documents(root) if d.meta.get("type") == "module"]


def continuation_documents(root: Path) -> list[Document]:
    return [d for d in project_documents(root) if d.meta.get("type") == "continuation"]


def source_inventory(root: Path, patterns: Iterable[str] | None = None) -> list[Path]:
    ignored = {".git", ".handoff", "__pycache__", ".venv", "build", "dist"}
    scan_roots: set[Path] = {root}
    direct_files: set[Path] = set()
    if patterns is not None:
        scan_roots.clear()
        for raw in patterns:
            pattern = str(raw).replace("\\", "/").lstrip("./")
            wildcard = min((pattern.find(ch) for ch in "*?[" if ch in pattern), default=-1)
            prefix = pattern[:wildcard] if wildcard >= 0 else pattern
            candidate = root / prefix.rstrip("/")
            if wildcard >= 0 and not candidate.is_dir():
                candidate = candidate.parent
            if candidate.is_file():
                direct_files.add(candidate)
            elif candidate.is_dir():
                scan_roots.add(candidate)
    files = set(direct_files)
    for scan_root in scan_roots:
        files.update(path for path in scan_root.rglob("*")
                     if path.is_file() and not ignored.intersection(path.parts))
    return sorted(files)


def _source_files(
    root: Path, patterns: Iterable[str], inventory: list[Path] | None = None,
) -> tuple[list[Path], list[str]]:
    files: set[Path] = set()
    missing: list[str] = []
    all_files = inventory
    for raw in patterns:
        pattern = str(raw).replace("\\", "/").lstrip("./")
        if any(ch in pattern for ch in "*?["):
            if all_files is None:
                all_files = source_inventory(root)
            matches = [p for p in all_files if fnmatch.fnmatch(p.relative_to(root).as_posix(), pattern)]
        else:
            target = root / pattern
            if target.is_file():
                matches = [target]
            elif target.is_dir():
                matches = ([p for p in all_files if target in p.parents] if all_files is not None
                           else [p for p in target.rglob("*") if p.is_file()])
            else:
                matches = []
        if not matches:
            missing.append(pattern)
        files.update(matches)
    return sorted(files), missing


def source_digest(
    root: Path, patterns: Iterable[str], inventory: list[Path] | None = None,
    digest_cache: dict[Path, bytes] | None = None,
) -> tuple[str, list[str], list[str]]:
    files, missing = _source_files(root, patterns, inventory)
    digest = hashlib.sha256()
    names: list[str] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        names.append(rel)
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        content_digest = digest_cache.get(path) if digest_cache is not None else None
        if content_digest is None:
            content_digest = hashlib.sha256(path.read_bytes()).digest()
            if digest_cache is not None:
                digest_cache[path] = content_digest
        digest.update(content_digest)
    return digest.hexdigest(), names, missing


def document_semantic_digest(meta: dict[str, Any], body: str) -> str:
    """Hash user-authored handoff meaning, excluding tool-maintained metadata."""
    semantic_meta = {key: value for key, value in meta.items()
                     if key not in SEMANTIC_DIGEST_EXCLUDED_FIELDS}
    payload = json.dumps({"meta": semantic_meta, "body": body}, ensure_ascii=False,
                         sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def module_status(
    root: Path, doc: Document, inventory: list[Path] | None = None,
    digest_cache: dict[Path, bytes] | None = None,
) -> dict[str, Any]:
    current, files, missing = source_digest(root, doc.meta.get("sources", []), inventory, digest_cache)
    baseline = verification_baseline(root, doc)
    verified = str(baseline.get("verified_digest", ""))
    if not verified:
        state = "UNVERIFIED"
        reason = "No verification baseline has been recorded."
    elif missing:
        state = "STALE"
        reason = "One or more source paths no longer resolve."
    elif current != verified:
        state = "STALE"
        reason = "Associated source content changed after verification."
    else:
        state = "FRESH"
        reason = "Associated source content matches the verification baseline."
    verified_document = str(baseline.get("verified_document_digest", ""))
    if verified_document:
        document_state = ("VERIFIED" if document_semantic_digest(doc.meta, doc.body) == verified_document
                          else "PENDING")
        document_reason = ("Current handoff content matches the semantic verification baseline."
                           if document_state == "VERIFIED"
                           else "Handoff content changed after semantic verification; review it again.")
    elif verified:
        document_state = "UNKNOWN_LEGACY"
        document_reason = "This older handoff has a source baseline but no semantic verification fingerprint."
    else:
        document_state = "UNVERIFIED"
        document_reason = "No semantic verification baseline has been recorded."
    return {
        "state": state, "reason": reason, "verified_at": baseline.get("verified_at"),
        "source_freshness": {"state": state, "digest": current},
        "external_checks": {"state": "NOT_CHECKED"},
        "updated_at": doc.meta.get("updated_at"), "source_count": len(files),
        "sources": files, "missing_sources": missing, "revision": doc.revision,
        "document_verification": {"state": document_state, "reason": document_reason},
    }


@contextmanager
def _verification_db():
    APP_HOME.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(INDEX)
    try:
        with db:
            db.execute("CREATE TABLE IF NOT EXISTS verification (root TEXT, id TEXT, value TEXT, PRIMARY KEY(root,id))")
            yield db
    finally:
        db.close()


def verification_baseline(root: Path, doc: Document) -> dict[str, Any]:
    if INDEX.exists():
        with _verification_db() as db:
            row = db.execute("SELECT value FROM verification WHERE root=? AND id=?",
                             (str(root.resolve()), doc.meta["id"])).fetchone()
        if row:
            return json.loads(row[0])
    return doc.meta  # Existing portable baselines remain readable.


@writer
def verify_module(root: Path, module_id: str, expected_revision: str | None = None) -> dict[str, Any]:
    doc = get_module(root, module_id)
    if expected_revision and doc.revision != expected_revision:
        raise RevisionConflict(doc, {}, expected_revision)
    digest, files, missing = source_digest(root, doc.meta.get("sources", []))
    if missing:
        raise ValueError("Cannot verify; missing source paths: " + ", ".join(missing))
    semantic = document_semantic_digest(doc.meta, doc.body)
    old = verification_baseline(root, doc)
    changed = old.get("verified_digest") != digest or old.get("verified_document_digest") != semantic
    verified_at = now_iso() if changed else old.get("verified_at")
    if changed:
        with _verification_db() as db:
            db.execute("INSERT OR REPLACE INTO verification VALUES (?,?,?)", (str(root.resolve()), module_id,
                       json.dumps({"verified_digest": digest, "verified_document_digest": semantic, "verified_at": verified_at})))
    revision = doc.revision
    return {"module_id": module_id, "state": "FRESH", "source_count": len(files),
            "verified_at": verified_at, "revision": revision, "changed": False,
            "verification_changed": changed, "verified": True, "external_checks": {"state": "NOT_CHECKED"}}


def get_module(root: Path, module_id: str) -> Document:
    direct = root / ".handoff" / "modules" / f"{module_id}.md"
    if direct.is_file():
        doc = parse_document(direct)
        if doc.meta.get("type") == "module" and doc.meta.get("id") == module_id:
            return doc
    for doc in module_documents(root):
        if doc.meta.get("id") == module_id:
            return doc
    raise KeyError(f"Unknown module '{module_id}'")


def get_document(root: Path, document_id: str, document_type: str | None = None) -> Document:
    matches = [d for d in project_documents(root)
               if d.meta.get("id") == document_id and (not document_type or d.meta.get("type") == document_type)]
    if not matches:
        raise KeyError(f"Unknown handoff document '{document_id}'")
    if len(matches) > 1:
        raise KeyError(f"Document id '{document_id}' is ambiguous; provide type.")
    return matches[0]


def validate_project(root: Path) -> list[str]:
    errors: list[str] = []
    docs = []
    seen: dict[str, Path] = {}
    for path in sorted((root / ".handoff").rglob("*.md")):
        if "archive" in path.parts:
            continue
        try:
            doc = parse_document(path)
            docs.append(doc)
            errors.extend(validate_document(doc))
            doc_id = str(doc.meta.get("id", ""))
            if doc_id in seen:
                errors.append(f"{path}: duplicate id '{doc_id}' also used by {seen[doc_id]}")
            elif doc_id:
                seen[doc_id] = path
        except (OSError, ValueError) as exc:
            errors.append(f"{path}: {exc}")
    module_ids = {str(d.meta["id"]) for d in docs if d.meta.get("type") == "module" and d.meta.get("id")}
    for doc in docs:
        if doc.meta.get("type") == "module":
            for relation in (*doc.meta.get("dependencies", []), *doc.meta.get("related_modules", [])):
                if relation not in module_ids:
                    errors.append(f"{doc.path}: related module '{relation}' does not exist")
            _, _, missing = source_digest(root, doc.meta.get("sources", []))
            for pattern in missing:
                errors.append(f"{doc.path}: source path has no matches: {pattern}")
        if doc.meta.get("type") == "continuation" and doc.meta.get("module_id") not in module_ids:
            errors.append(f"{doc.path}: continuation module_id '{doc.meta.get('module_id')}' does not exist")
    return errors


def rebuild_index(root: Path) -> dict[str, int]:
    APP_HOME.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(INDEX)
    try:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
          project_root TEXT NOT NULL, doc_id TEXT NOT NULL, doc_type TEXT NOT NULL,
          title TEXT NOT NULL, summary TEXT NOT NULL, aliases TEXT NOT NULL,
          tags TEXT NOT NULL, body TEXT NOT NULL, path TEXT NOT NULL, revision TEXT NOT NULL,
          PRIMARY KEY(project_root, doc_id)
        );
        DELETE FROM documents WHERE project_root = ?;
        """.replace("DELETE FROM documents WHERE project_root = ?;", ""))
        db.execute("DELETE FROM documents WHERE project_root = ?", (str(root),))
        docs = project_documents(root)
        for doc in docs:
            db.execute(
                "INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)",
                (str(root), str(doc.meta.get("id", "")), str(doc.meta.get("type", "")),
                 str(doc.meta.get("title", "")), str(doc.meta.get("summary", "")),
                 json.dumps(doc.meta.get("aliases", []), ensure_ascii=False),
                 json.dumps(doc.meta.get("tags", []), ensure_ascii=False), doc.body,
                 str(doc.path), doc.revision),
            )
        db.commit()
    finally:
        db.close()
    return {"documents": len(docs), "modules": len([d for d in docs if d.meta.get("type") == "module"])}


def search(
    root: Path, query: str, limit: int = 20, include_next: bool = True,
    documents: list[Document] | None = None,
) -> list[dict[str, Any]]:
    lowered = query.lower().strip()
    terms = [t for t in re.split(r"\s+", lowered) if t]
    cjk_runs = re.findall(r"[\u3400-\u9fff]+", lowered)
    for run in cjk_runs:
        if len(run) >= 2:
            terms.extend(run[i:i + 2] for i in range(len(run) - 1))
    terms = [t for t in dict.fromkeys(terms) if not re.fullmatch(r"[\dv.\-]+", t)]
    ranked = []
    for doc in documents if documents is not None else project_documents(root):
        title = str(doc.meta.get("title", ""))
        summary = str(doc.meta.get("summary", ""))
        aliases = " ".join(map(str, doc.meta.get("aliases", [])))
        tags = " ".join(map(str, doc.meta.get("tags", [])))
        fields = [(title.lower(), 12), (aliases.lower(), 12), (tags.lower(), 10), (summary.lower(), 6),
                  (" ".join(map(str, doc.meta.get("sources", []))).lower(), 9),
                  (" ".join(map(str, doc.meta.get("dependencies", []))).lower(), 8)]
        body = "\n".join(line for line in doc.body.lower().splitlines()
                         if not re.search(r"\b\d+\.\d+\.\d+\b|\b20\d\d[-/]\d|sha256|apk.*hash", line))
        score = sum(weight for term in terms for text, weight in fields if term in text)
        score += min(2, sum(1 for term in terms if term in body))
        if not terms or score:
            ranked.append((score, doc))
    ranked.sort(key=lambda item: (-item[0], str(item[1].meta.get("title", ""))))
    project_id = parse_document(root / ".handoff" / "overview.md").meta.get("id")
    results = []
    for score, doc in ranked[:limit]:
        result = {"id": doc.meta.get("id"), "type": doc.meta.get("type"), "title": doc.meta.get("title"),
                  "summary": doc.meta.get("summary"), "score": score, "revision": doc.revision}
        matched_fields = []
        for name, text in (("title", str(doc.meta.get("title", ""))),
                           ("aliases", " ".join(map(str, doc.meta.get("aliases", [])))),
                           ("tags", " ".join(map(str, doc.meta.get("tags", [])))),
                           ("summary", str(doc.meta.get("summary", ""))),
                           ("sources", " ".join(map(str, doc.meta.get("sources", [])))),
                           ("dependencies", " ".join(map(str, doc.meta.get("dependencies", [])))), ("body", doc.body)):
            if any(term in text.lower() for term in terms):
                matched_fields.append(name)
        result["match_reason"] = {"fields": matched_fields,
                                  "snippet": next((line.strip()[:160] for line in doc.body.splitlines()
                                                   if any(term in line.lower() for term in terms)), None)}
        if include_next:
            result["next_action"] = {"tool": f"{doc.meta.get('type')}_get", "arguments": {
                "project": str(root.resolve()), "id": doc.meta.get("id"), "full": True,
            }}
        results.append(result)
    return results


def resolve_task(root: Path, task: str, limit: int = 3, detail: str = "concise") -> dict[str, Any]:
    if detail not in ("concise", "detailed"):
        raise ValueError("detail must be 'concise' or 'detailed'")
    overview = parse_document(root / ".handoff" / "overview.md")
    project_id = overview.meta.get("id")
    documents = project_documents(root)
    ranked = [r for r in search(root, task, max(limit * 3, len(documents)), documents=documents)
              if r["type"] == "module"]
    if ranked:
        cutoff = max(3, ranked[0]["score"] * 0.25)
        results = [r for r in ranked if r["score"] >= cutoff][:limit]
    else:
        results = []
    continuations = [d for d in documents if d.meta.get("type") == "continuation"]
    modules = {str(d.meta.get("id")): d for d in documents if d.meta.get("type") == "module"}
    selected_docs = [modules[str(result["id"])] for result in results]
    dependency_ids = list(dict.fromkeys(
        str(dep) for doc in selected_docs for dep in doc.meta.get("dependencies", [])
    ))
    existing_dependency_ids = [dep for dep in dependency_ids if dep in modules]
    status_docs = selected_docs + [modules[dep] for dep in existing_dependency_ids]
    patterns = [pattern for doc in status_docs for pattern in doc.meta.get("sources", [])]
    inventory = source_inventory(root, patterns)
    digest_cache: dict[Path, bytes] = {}
    statuses = {str(doc.meta.get("id")): module_status(root, doc, inventory, digest_cache)
                for doc in status_docs}
    dependency_summaries = []
    for dep in dependency_ids:
        if dep not in modules:
            dependency_summaries.append({"id": dep, "missing": True})
            continue
        dep_doc, dep_status = modules[dep], statuses[dep]
        summary = {"id": dep, "title": dep_doc.meta.get("title"), "summary": dep_doc.meta.get("summary"),
                   "recommendation": "related",
                   "freshness": dep_status["state"],
                   "document_verification": dep_status["document_verification"]}
        if detail == "detailed":
            summary.update({"sources": dep_doc.meta.get("sources", []),
                            "missing_sources": dep_status["missing_sources"], "revision": dep_doc.revision})
        dependency_summaries.append(summary)
    for result in results:
        doc = modules[str(result["id"])]
        full_status = statuses[str(result["id"])]
        resolved_sources = full_status["sources"]
        if detail == "detailed":
            result["freshness"] = {**full_status, "resolved_source_sample": resolved_sources[:8],
                                   "omitted_source_count": max(0, len(resolved_sources) - 8)}
            result["freshness"].pop("sources", None)
            result["sources"] = doc.meta.get("sources", [])
        else:
            result["freshness"] = {key: full_status[key] for key in
                                   ("state", "reason", "document_verification", "missing_sources")}
            result["source_patterns"] = doc.meta.get("sources", [])
            result.pop("score", None)
        result["business_rules"] = doc.meta.get("business_rules", [])
        result["invariants"] = doc.meta.get("invariants", [])
        result["consumers"] = doc.meta.get("consumers", [])
        result["dependencies"] = [str(dep) for dep in doc.meta.get("dependencies", [])]
        result["related_modules"] = doc.meta.get("related_modules", [])
        strong = set(result["match_reason"]["fields"]) & {"title", "aliases", "tags", "sources"}
        modifying = bool(re.search(r"更新|修改|修复|优化|上传|发布|update|fix|change|upload|release", task, re.I))
        result["recommendation"] = "modify" if strong and modifying else "read"
        result["open_continuations"] = [
            {"id": c.meta.get("id"), "title": c.meta.get("title"), "next_step": c.meta.get("next_step"),
             "revision": c.revision, "status": c.meta.get("status"), "external_checks": c.meta.get("external_checks", [])}
            for c in continuations if c.meta.get("module_id") == result["id"] and c.meta.get("status") != "done"
        ]
        result.pop("next_action", None)
    return {"task": task, "project": {"id": overview.meta.get("id"), "title": overview.meta.get("title"), "path": str(root)},
            "project_context": {"summary": overview.meta.get("summary"),
                                 "architecture": overview.meta.get("architecture_summary", overview.meta.get("summary", ""))},
            "matches": results, "dependency_summaries": dependency_summaries,
            "next_actions": ([{"tool": "module_get_many", "arguments": {"project": str(root.resolve()),
                                "ids": [r["id"] for r in results], "full": True}}]
                             if results else [{"tool": "search", "arguments": {"project": str(root.resolve()), "query": task}}])}


@writer
def save_module(root: Path, payload: dict[str, Any], expected_revision: str | None = None) -> dict[str, Any]:
    module_id = str(payload.get("id", "")).strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", module_id):
        raise ValueError("Invalid module id")
    path = root / ".handoff" / "modules" / f"{module_id}.md"
    try:
        current = get_module(root, module_id)
        path = current.path
    except KeyError:
        current = None
    if current is not None:
        if expected_revision == "new":
            raise FileExistsError(f"Module '{module_id}' already exists")
        if not expected_revision:
            raise RuntimeError("expected_revision is required when updating an existing module.")
        if current.revision != expected_revision:
            raise RevisionConflict(current, payload, expected_revision)
    elif path.exists():
        raise FileExistsError(f"Target path contains another document: {path}")
    elif expected_revision not in (None, "new"):
        raise RuntimeError(f"Module '{module_id}' no longer exists; use expected_revision='new' only to intentionally recreate it.")

    list_fields = ("aliases", "tags", "sources", "dependencies", "related_modules",
                   "business_rules", "invariants", "consumers")
    meta = dict(current.meta) if current else {
        "schema_version": 1, "type": "module", "id": module_id,
        "title": module_id, "summary": "", "aliases": [], "tags": [], "sources": [],
        "dependencies": [], "related_modules": [], "business_rules": [], "invariants": [],
        "consumers": [],
    }
    meta.update({"schema_version": 1, "type": "module", "id": module_id})
    for field in ("title", "summary", *list_fields):
        if field in payload:
            meta[field] = payload[field]
    body = str(payload["body"]) if "body" in payload else (current.body if current else "")

    # An update that does not change user-authored content is a true no-op: keep
    # timestamps, verification metadata, bytes on disk and therefore revision.
    if current and meta == current.meta and body.rstrip("\r\n") == current.body.rstrip("\r\n"):
        return {"id": module_id, "path": str(path), "revision": current.revision, "changed": False}

    meta["updated_at"] = now_iso()
    preview = Document(path, meta, body)
    errors = validate_document(preview)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_document(path, meta, body)
    rebuild_index(root)
    result = {"id": module_id, "path": str(path), "revision": parse_document(path).revision,
              "changed": True}
    if re.search(r"本次|尚未完成|等待|重试|临时失败|下一步|\b(?:retry|pending|next step)\b", body, re.I):
        result["warnings"] = ["Temporary progress belongs in continuation_save; release facts belong in CHANGELOG/release records."]
    return result


@writer
def archive_module(root: Path, module_id: str, expected_revision: str | None = None) -> dict[str, Any]:
    doc = get_module(root, module_id)
    if expected_revision and doc.revision != expected_revision:
        raise RuntimeError("Document changed since it was read; reload before archiving.")
    archive = root / ".handoff" / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    target = archive / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{doc.path.name}"
    shutil.move(str(doc.path), str(target))
    rebuild_index(root)
    return {"id": module_id, "archived_to": str(target), "revision": parse_document(target).revision}


@writer
def save_continuation(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    task_id = str(payload.get("id", "")).strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", task_id):
        raise ValueError("Invalid continuation id")
    path = root / ".handoff" / "continuations" / f"{task_id}.md"
    current = parse_document(path) if path.exists() else None
    if current:
        if payload.get("expected_revision") != current.revision:
            raise RevisionConflict(current, payload, payload.get("expected_revision"))
        payload = {**current.meta, "body": current.body, **payload}
    meta = {
        "schema_version": 1, "type": "continuation", "id": task_id,
        "title": payload.get("title", task_id), "module_id": payload.get("module_id", ""),
        "status": payload.get("status", "open"), "next_step": payload.get("next_step", ""),
        "updated_at": now_iso(),
    }
    body = str(payload.get("body", ""))
    if meta["status"] not in ("open", "blocked", "done"):
        raise ValueError("Invalid continuation status")
    get_module(root, str(meta["module_id"]))
    if "external_checks" in payload:
        meta["external_checks"] = payload["external_checks"]
    if current and document_semantic_digest(meta, body.rstrip("\r\n")) == document_semantic_digest(current.meta, current.body.rstrip("\r\n")):
        return {"id": task_id, "revision": current.revision, "changed": False, "status": meta["status"]}
    preview = Document(path, meta, body)
    errors = validate_document(preview)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_document(path, meta, body)
    rebuild_index(root)
    return {"id": task_id, "path": str(path), "revision": parse_document(path).revision, "changed": True, "status": meta["status"]}


class RevisionConflict(RuntimeError):
    def __init__(self, current, payload, expected):
        from difflib import unified_diff
        self.details = {"code": "revision_conflict", "id": current.meta["id"],
                        "expected_revision": expected, "revision": current.revision,
                        "message": "Reload affected fields and reapply; diff compares current with requested content, not the unavailable old base.",
                        "fields": {k: {"current": current.meta.get(k), "requested": v}
                                   for k, v in payload.items() if k in current.meta and current.meta[k] != v}}
        if "body" in payload:
            self.details["diff"] = "".join(unified_diff(current.body.splitlines(True), str(payload["body"]).splitlines(True),
                                                      fromfile="current", tofile="requested"))[:4000]
        super().__init__("Document changed since it was read; reload before saving.")


@writer
def patch_module(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Replace unique Markdown sections; preserve all surrounding bytes in the body."""
    doc = get_module(root, str(payload["id"]))
    if payload.get("expected_revision") != doc.revision:
        conflict = RevisionConflict(doc, payload.get("fields", {}), payload.get("expected_revision"))
        if payload.get("sections"):
            conflict.details["requested_sections"] = payload["sections"]
            conflict.details["current_body_excerpt"] = doc.body[:4000]
        raise conflict
    fields = dict(payload.get("fields", {}))
    allowed = {"title", "summary", "aliases", "tags", "sources", "dependencies", "related_modules",
               "business_rules", "invariants", "consumers"}
    if set(fields) - allowed:
        raise ValueError("Unsupported patch fields: " + ", ".join(sorted(set(fields) - allowed)))
    body = doc.body
    for section in payload.get("sections", []):
        lines = body.splitlines(keepends=True)
        headings = []
        fence = None
        for i, line in enumerate(lines):
            fenced = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
            if fenced:
                marker = fenced[1]
                if fence is None:
                    fence = marker
                elif marker[0] == fence[0] and len(marker) >= len(fence):
                    fence = None
                continue
            match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line) if fence is None else None
            if match:
                headings.append((i, len(match[1]), match[2]))
        matches = [h for h in headings if h[2] == section["heading"]]
        if len(matches) != 1:
            raise ValueError(f"Section '{section['heading']}' must match exactly one ATX heading; found {len(matches)}")
        start, level, _ = matches[0]
        end = next((i for i, depth, _ in headings if i > start and depth <= level), len(lines))
        content = str(section["body"])
        body = "".join(lines[:start + 1]) + "\n" + content.rstrip("\r\n") + "\n\n" + "".join(lines[end:])
    return save_module.__wrapped__(root, {"id": payload["id"], **fields, "body": body}, doc.revision)


@writer
def save_and_verify(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    # Hold one writer lock across the save and optional attestation.
    if ("sections" in payload or "fields" in payload) and any(k in payload for k in
            ("body", "title", "summary", "aliases", "tags", "sources", "dependencies", "related_modules", "business_rules", "invariants", "consumers")):
        raise ValueError("Use either patch fields/sections or save fields/body in one change, not both")
    operation = patch_module if "sections" in payload or "fields" in payload else save_module
    result = (operation.__wrapped__(root, payload) if operation is patch_module else
              operation.__wrapped__(root, payload, payload.get("expected_revision")))
    if payload.get("verify", False):
        try:
            verified = verify_module.__wrapped__(root, str(payload["id"]), result["revision"])
            result.update({k: v for k, v in verified.items() if k not in ("changed", "module_id")})
        except (ValueError, OSError) as exc:
            result.update({"verified": False, "verification_error": str(exc)})
    else:
        result["verified"] = module_status(root, get_module(root, str(payload["id"])))['document_verification']['state'] == "VERIFIED"
    return result


@writer
def import_bundle(root: Path, source: Path, replace: bool = False) -> dict[str, Any]:
    candidates = sorted(source.rglob("*.md")) if source.is_dir() else [source]
    parsed: list[Document] = []
    errors: list[str] = []
    for path in candidates:
        try:
            doc = parse_document(path)
            errors.extend(validate_document(doc))
            parsed.append(doc)
        except (OSError, ValueError) as exc:
            errors.append(f"{path}: {exc}")
    ids = [str(d.meta.get("id", "")) for d in parsed]
    for value in set(ids):
        if ids.count(value) > 1:
            errors.append(f"duplicate id in import bundle: {value}")
    known = {str(d.meta.get("id")) for d in module_documents(root)} | {str(d.meta.get("id")) for d in parsed if d.meta.get("type") == "module"}
    for doc in parsed:
        if doc.meta.get("type") == "module":
            for rel in (*doc.meta.get("dependencies", []), *doc.meta.get("related_modules", [])):
                if rel not in known:
                    errors.append(f"{doc.path}: related module '{rel}' does not exist")
            _, _, missing = source_digest(root, doc.meta.get("sources", []))
            for item in missing:
                errors.append(f"{doc.path}: source path has no matches: {item}")
    if errors:
        return {"imported": 0, "errors": errors}
    imported = 0
    for doc in parsed:
        if doc.meta.get("type") == "overview":
            target = root / ".handoff" / "overview.md"
        elif doc.meta.get("type") == "module":
            target = root / ".handoff" / "modules" / f"{doc.meta['id']}.md"
        else:
            target = root / ".handoff" / "continuations" / f"{doc.meta['id']}.md"
        if target.exists() and not replace:
            return {"imported": imported, "errors": [f"target exists: {target}; use --replace to overwrite"]}
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(doc.path, target)
        imported += 1
    register_project(root)
    rebuild_index(root)
    return {"imported": imported, "errors": []}
