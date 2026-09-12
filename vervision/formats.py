from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED = {
    "overview": ("schema_version", "type", "id", "title", "summary"),
    "module": ("schema_version", "type", "id", "title", "summary", "sources"),
    "continuation": ("schema_version", "type", "id", "title", "module_id", "status", "next_step"),
}


@dataclass
class Document:
    path: Path
    meta: dict[str, Any]
    body: str

    @property
    def revision(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()[:16]


def _value(raw: str) -> Any:
    raw = raw.strip()
    if raw in ("", "null", "~"):
        return "" if raw == "" else None
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if raw.startswith(("[", "{", '"')):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return raw.strip("'\"")


def parse_document(path: Path) -> Document:
    text = path.read_text(encoding="utf-8-sig")
    if not text.startswith("---"):
        raise ValueError("missing YAML frontmatter opener '---'")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("missing YAML frontmatter closer '---'")
    meta: dict[str, Any] = {}
    pending_list: str | None = None
    for line_no, line in enumerate(parts[1].splitlines(), 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith(("  - ", "- ")) and pending_list:
            meta[pending_list].append(_value(line.split("-", 1)[1]))
            continue
        if ":" not in line:
            raise ValueError(f"frontmatter line {line_no} must be key: value")
        key, raw = line.split(":", 1)
        key = key.strip()
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            raise ValueError(f"invalid key '{key}' on line {line_no}")
        if not raw.strip():
            meta[key] = []
            pending_list = key
        else:
            meta[key] = _value(raw)
            pending_list = None
    return Document(path=path, meta=meta, body=parts[2].lstrip("\r\n"))


def dump_document(meta: dict[str, Any], body: str) -> str:
    lines = ["---"]
    for key, value in meta.items():
        if isinstance(value, (list, dict)):
            rendered = json.dumps(value, ensure_ascii=False)
        elif value is None:
            rendered = "null"
        elif isinstance(value, bool):
            rendered = str(value).lower()
        elif isinstance(value, (int, float)):
            rendered = str(value)
        else:
            rendered = json.dumps(str(value), ensure_ascii=False)
        lines.append(f"{key}: {rendered}")
    # Only normalize terminal newlines. Trailing spaces can be meaningful in Markdown
    # (for example, two spaces before a newline produce a hard line break).
    lines.extend(["---", "", body.rstrip("\r\n"), ""])
    return "\n".join(lines)


def validate_document(doc: Document) -> list[str]:
    errors: list[str] = []
    kind = str(doc.meta.get("type", ""))
    if kind not in REQUIRED:
        return [f"{doc.path}: type must be overview, module, or continuation"]
    for field in REQUIRED[kind]:
        if doc.meta.get(field) in (None, "", []):
            errors.append(f"{doc.path}: missing required field '{field}'")
    if doc.meta.get("schema_version") != 1:
        errors.append(f"{doc.path}: unsupported schema_version (expected 1)")
    doc_id = str(doc.meta.get("id", ""))
    if doc_id and not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", doc_id):
        errors.append(f"{doc.path}: id must use lowercase letters, numbers, '.', '_' or '-'")
    for field in ("aliases", "tags", "sources", "dependencies", "related_modules",
                  "business_rules", "invariants", "consumers"):
        if field in doc.meta and not isinstance(doc.meta[field], list):
            errors.append(f"{doc.path}: '{field}' must be a JSON-style array")
    return errors
