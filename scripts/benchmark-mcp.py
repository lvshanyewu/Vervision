"""Compare a two-module maintenance workflow against a git revision, in temporary projects.

Run: python scripts/benchmark-mcp.py [baseline-ref]
Reports serialized response characters, not an estimate of model-specific tokens.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[1]
RUNNER = r'''
import json, sys
from pathlib import Path
from vervision.core import init_project, save_module, get_module
from vervision.mcp_server import call_tool
root = Path(sys.argv[1])
init_project(root, "bench", "Android release")
(root / "release.py").write_text("VERSION = 1\n")
for name in ("release-engineering", "settings-update"):
    save_module(root, {"id": name, "title": name, "summary": "OpenList release settings", "aliases": ["OpenList"],
                      "sources": ["release.py"], "body": "# Stable rules\n\n" + "Preserve release configuration and signing rules.\n" * 30}, "new")
responses=[]
if sys.argv[2] == "old":
    responses.append(call_tool("resolve", {"project": str(root), "task": "OpenList release settings"}))
    for name in ("release-engineering", "settings-update"):
        responses.append(call_tool("handoff_get", {"project": str(root), "type": "module", "id": name, "full": True}))
    for name in ("release-engineering", "settings-update"):
        doc=get_module(root,name)
        responses.append(call_tool("module_save", {"project": str(root), "id": name, "body": doc.body, "expected_revision": doc.revision}))
        responses.append(call_tool("module_verify", {"project": str(root), "module_id": name, "expected_revision": responses[-1]["revision"]}))
    wire=[{"content":[{"type":"text","text":json.dumps(r,ensure_ascii=False,indent=2)}],"isError":False} for r in responses]
else:
    resolved=call_tool("resolve", {"project": str(root), "task": "OpenList release settings"})
    responses.append(resolved)
    scope=resolved["scope_id"]
    responses.append(call_tool("module_get_many", {"scope_id":scope, "ids":["release-engineering","settings-update"], "full":True}))
    responses.append(call_tool("module_save_many", {"scope_id":scope, "changes":[{"id":name,"expected_revision":get_module(root,name).revision,"verify":True} for name in ("release-engineering","settings-update")]}))
    wire=[{"structuredContent":r,"content":[{"type":"text","text":"Vervision result is in structuredContent."}],"isError":False} for r in responses]
print(json.dumps({"calls":len(responses),"response_characters":sum(len(json.dumps(r,ensure_ascii=False,separators=(",",":"))) for r in wire)}))
'''


def main():
    ref = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        old = base / "old" / "vervision"
        old.mkdir(parents=True)
        for name in ("__init__.py", "core.py", "formats.py", "mcp_server.py"):
            content = subprocess.check_output(["git", "show", f"{ref}:vervision/{name}"], cwd=REPO)
            (old / name).write_bytes(content)
        results = {}
        for mode, code in (("old", old.parent), ("new", REPO)):
            env = {**os.environ, "LOCALAPPDATA": str(base / mode / "appdata"), "PYTHONPATH": str(code)}
            output = subprocess.check_output([sys.executable, "-c", RUNNER, str(base / mode / "project"), mode],
                                             cwd=base, env=env, text=True, encoding="utf-8")
            results[mode] = json.loads(output)
        results["response_reduction_percent"] = round(100 * (1 - results["new"]["response_characters"] / results["old"]["response_characters"]), 1)
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
