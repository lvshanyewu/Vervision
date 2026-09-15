import json
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import test_core
from vervision import core
from vervision.mcp_server import call_tool, SCOPES, TOOLS


class WorkflowTests(unittest.TestCase):
    setUp = test_core.CoreTests.setUp
    tearDown = test_core.CoreTests.tearDown

    def scope(self):
        return call_tool("resolve", {"workspace": str(self.root), "task": "更新 Feature"})

    def test_scope_and_batch_next_action(self):
        result = self.scope()
        self.assertNotIn("project_selection", result)
        self.assertIn("revision", result["matches"][0])
        action = result["next_actions"][0]
        read = call_tool(action["tool"], action["arguments"])
        self.assertEqual(read["results"][0]["id"], "feature")
        self.assertNotIn("project_selection", read["results"][0])
        value = call_tool("module_get", {"scope_id": result["scope_id"], "id": "feature"})
        self.assertNotIn("body", value)
        self.assertIn("source_freshness", value)
        self.assertIn("body", call_tool("module_get", {"scope_id": result["scope_id"], "id": "feature", "full": True}))

    def test_invalid_scope_and_mismatched_workspace(self):
        with self.assertRaisesRegex(ValueError, "expired"):
            call_tool("module_get", {"scope_id": "invalid", "id": "feature"})
        scope = self.scope()["scope_id"]
        with self.assertRaisesRegex(ValueError, "conflicts"):
            call_tool("module_save", {"scope_id": scope, "workspace": str(self.root.parent), "id": "feature"})

    def test_multiple_roots_do_not_select_the_deeper_project(self):
        other = self.root / "nested" / "other"
        core.init_project(other, "other", "Other")
        result = core.select_project(workspaces=[self.root, other])
        self.assertIsNone(result["selected"])

    def test_document_revision_refers_to_read_snapshot(self):
        doc = core.get_module(self.root, "feature")
        revision = doc.revision
        core.save_module(self.root, {"id": "feature", "body": "New"}, revision)
        self.assertEqual(doc.revision, revision)
        self.assertNotEqual(core.get_module(self.root, "feature").revision, revision)

    def test_stale_save_does_not_recreate_deleted_module(self):
        doc = core.get_module(self.root, "feature")
        doc.path.unlink()
        with self.assertRaisesRegex(RuntimeError, "no longer exists"):
            core.save_module(self.root, {"id": "feature", "summary": "new", "sources": ["src/feature.py"]}, doc.revision)
        self.assertFalse(doc.path.exists())

    def test_save_preserves_existing_noncanonical_filename(self):
        doc = core.get_module(self.root, "feature")
        renamed = doc.path.with_name("custom.md")
        doc.path.rename(renamed)
        core.save_module(self.root, {"id": "feature", "summary": "Updated"}, doc.revision)
        self.assertEqual(core.get_module(self.root, "feature").path, renamed)
        self.assertFalse(doc.path.exists())

    def test_ambiguous_write_cannot_use_unique_document_or_task_score(self):
        other = self.root / "other"
        core.init_project(other, "other", "Other")
        notes = self.root / "notes"
        notes.mkdir()
        (self.root / ".handoff" / "overview.md").unlink()
        first = self.root / "first"
        core.init_project(first, "first", "First")
        core.save_module(first, {"id": "unique", "summary": "OpenList upload", "sources": [".handoff/overview.md"]}, "new")
        with self.assertRaises(FileNotFoundError):
            call_tool("module_save", {"workspace": str(notes), "id": "unique", "body": "wrong"})

    def test_verify_is_idempotent_and_does_not_touch_markdown(self):
        doc = core.get_module(self.root, "feature")
        before, stamp = doc.path.read_bytes(), doc.path.stat().st_mtime_ns
        first = core.verify_module(self.root, "feature", doc.revision)
        second = core.verify_module(self.root, "feature", doc.revision)
        self.assertTrue(first["verification_changed"])
        self.assertFalse(second["verification_changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(first["verified_at"], second["verified_at"])
        self.assertEqual(doc.path.read_bytes(), before)
        self.assertEqual(doc.path.stat().st_mtime_ns, stamp)
        self.assertEqual(first["revision"], doc.revision)
        core.rebuild_index(self.root)
        self.assertEqual(core.module_status(self.root, doc)["document_verification"]["state"], "VERIFIED")

    def test_patch_preserves_paths_fences_and_unrelated_sections(self):
        doc = core.get_module(self.root, "feature")
        body = '# Paths\n\nD:\\AndroidStudio\n\n# Status\n\nold\n\n# Other\n\n```md\n# Status\n```\nKeep 77.  \n'
        saved = core.save_module(self.root, {"id": "feature", "body": body}, doc.revision)
        args = {"project": str(self.root), "id": "feature", "expected_revision": saved["revision"],
                "sections": [{"heading": "Status", "body": "Uploaded."}]}
        patched = call_tool("module_patch", args)
        after = core.get_module(self.root, "feature")
        self.assertEqual(after.body, body.replace("old", "Uploaded."))
        repeated = call_tool("module_patch", {**args, "expected_revision": patched["revision"]})
        self.assertFalse(repeated["changed"])
        self.assertEqual(repeated["revision"], patched["revision"])

    def test_patch_rejects_ambiguous_heading_without_writing(self):
        doc = core.get_module(self.root, "feature")
        saved = core.save_module(self.root, {"id": "feature", "body": "# Same\nA\n# Same\nB\n"}, doc.revision)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            call_tool("module_patch", {"project": str(self.root), "id": "feature", "expected_revision": saved["revision"],
                                      "sections": [{"heading": "Same", "body": "C"}]})
        self.assertEqual(core.get_module(self.root, "feature").revision, saved["revision"])

    def test_batch_partial_conflict_and_final_revision(self):
        doc = core.get_module(self.root, "feature")
        result = call_tool("module_save_many", {"project": str(self.root), "changes": [
            {"id": "feature", "body": "bad", "expected_revision": "stale"},
            {"id": "release", "summary": "Release", "sources": ["src/feature.py"], "body": "Stable rule", "verify": True}]})
        self.assertEqual(result["mode"], "partial")
        self.assertFalse(result["ok"])
        failed, saved = result["results"]
        self.assertEqual(failed["error"]["revision"], doc.revision)
        self.assertIn("diff", failed["error"])
        self.assertTrue(saved["verified"])
        self.assertEqual(saved["revision"], core.get_module(self.root, "release").revision)
        self.assertEqual(core.get_module(self.root, "feature").revision, doc.revision)

    def test_save_verification_failure_reports_saved_document(self):
        doc = core.get_module(self.root, "feature")
        result = call_tool("module_save_and_verify", {"project": str(self.root), "id": "feature", "expected_revision": doc.revision,
                                                      "sources": ["missing.py"]})
        self.assertTrue(result["changed"])
        self.assertFalse(result["verified"])
        self.assertIn("verification_error", result)
        self.assertEqual(result["revision"], core.get_module(self.root, "feature").revision)

    def test_save_and_verify_same_revision_reusable(self):
        doc = core.get_module(self.root, "feature")
        args = {"project": str(self.root), "id": "feature", "expected_revision": doc.revision, "body": "Updated"}
        first = call_tool("module_save_and_verify", args)
        second = call_tool("module_save_and_verify", {**args, "expected_revision": first["revision"]})
        self.assertFalse(second["changed"])
        self.assertFalse(second["verification_changed"])
        self.assertEqual(first["revision"], second["revision"])

    def test_continuation_done_is_partial_and_external_checks_are_separate(self):
        args = {"project": str(self.root), "id": "upload", "module_id": "feature", "title": "Upload",
                "status": "blocked", "next_step": "Retry", "body": "Temporary failure",
                "external_checks": [{"service": "OpenList", "status": "failed", "evidence": "HTTP 503", "checked_at": "2026-09-12T12:00:00Z"}]}
        saved = call_tool("continuation_save", args)
        done = call_tool("continuation_save", {"project": str(self.root), "id": "upload", "status": "done"})
        doc = core.get_document(self.root, "upload", "continuation")
        self.assertEqual(doc.body, "Temporary failure\n")
        self.assertEqual(done["status"], "done")
        self.assertEqual(self.scope()["matches"][0]["open_continuations"], [])
        core.verify_module(self.root, "feature")
        self.assertEqual(core.module_status(self.root, core.get_module(self.root, "feature"))["external_checks"]["state"], "NOT_CHECKED")

    def test_continuation_direct_update_preserves_extensions_and_is_idempotent(self):
        args = {"project": str(self.root), "id": "task", "module_id": "feature", "next_step": "Review", "body": "Notes"}
        call_tool("continuation_save", args)
        doc = core.get_document(self.root, "task", "continuation")
        core._write_document(doc.path, {**doc.meta, "extension_note": "Keep"}, doc.body)
        updated = call_tool("continuation_save", {"project": str(self.root), "id": "task", "status": "done"})
        before, stamp = doc.path.read_bytes(), doc.path.stat().st_mtime_ns
        repeated = call_tool("continuation_save", {"project": str(self.root), "id": "task", "status": "done"})
        self.assertFalse(repeated["changed"])
        self.assertEqual(updated["revision"], repeated["revision"])
        self.assertEqual(doc.path.read_bytes(), before)
        self.assertEqual(doc.path.stat().st_mtime_ns, stamp)
        after = core.get_document(self.root, "task", "continuation")
        self.assertEqual(after.meta["extension_note"], "Keep")
        self.assertEqual(after.body, "Notes\n")

    def test_continuation_revision_guards_create_update_and_deletion(self):
        args = {"project": str(self.root), "id": "task", "module_id": "feature", "next_step": "Review", "expected_revision": "new"}
        saved = call_tool("continuation_save", args)
        with self.assertRaises(core.RevisionConflict):
            call_tool("continuation_save", args)
        updated = call_tool("continuation_save", {**args, "expected_revision": saved["revision"], "next_step": "Test"})
        with self.assertRaises(core.RevisionConflict) as caught:
            call_tool("continuation_save", {**args, "expected_revision": saved["revision"]})
        self.assertEqual(caught.exception.details["revision"], updated["revision"])
        doc = core.get_document(self.root, "task", "continuation")
        doc.path.unlink()
        with self.assertRaisesRegex(RuntimeError, "no longer exists"):
            call_tool("continuation_save", {**args, "expected_revision": updated["revision"]})
        self.assertFalse(doc.path.exists())

    def test_continuation_concurrent_partial_updates_and_guarded_writers(self):
        args = {"id": "task", "module_id": "feature", "next_step": "Review"}
        core.save_continuation(self.root, args)
        def write(fields):
            return core.save_continuation(self.root, {"id": "task", **fields})
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(write, [{"status": "blocked"}, {"next_step": "Retry"}]))
        doc = core.get_document(self.root, "task", "continuation")
        self.assertEqual(doc.meta["status"], "blocked")
        self.assertEqual(doc.meta["next_step"], "Retry")
        def guarded(body):
            try:
                return write({"body": body, "expected_revision": doc.revision})["changed"]
            except core.RevisionConflict:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(guarded, ["First", "Second"])), [False, True])

    def test_ranking_ignores_release_log_as_modification_target(self):
        core.save_module(self.root, {"id": "release", "title": "Release engineering", "aliases": ["OpenList 上传"],
                                    "summary": "发布渠道", "sources": ["src/feature.py"]}, "new")
        core.save_module(self.root, {"id": "workout", "title": "Workout", "summary": "训练", "sources": ["src/feature.py"],
                                    "body": "\n".join(["1.0.4 APK OpenList 上传状态更新成功"] * 100)}, "new")
        result = self.scope()
        result = call_tool("resolve", {"workspace": str(self.root), "task": "OpenList 上传状态更新"})
        self.assertEqual(result["matches"][0]["id"], "release")
        self.assertEqual(result["matches"][0]["recommendation"], "modify")
        self.assertNotIn("workout", [m["id"] for m in result["matches"]])

    def test_schema_rejects_wrong_types_and_batch_scope(self):
        with self.assertRaises(ValueError):
            call_tool("module_save_many", {"project": str(self.root), "changes": [{"id": "feature", "project": "elsewhere"}]})
        with self.assertRaises(ValueError):
            call_tool("module_patch", {"project": str(self.root), "id": "feature", "expected_revision": "x", "fields": {"tags": "wrong"}})

    def test_concurrent_writers_only_one_accepts_revision(self):
        revision = core.get_module(self.root, "feature").revision
        def write(body):
            try:
                return core.save_module(self.root, {"id": "feature", "body": body}, revision)["changed"]
            except core.RevisionConflict:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, ["First", "Second"]))
        self.assertEqual(sorted(results), [False, True])

    def test_stdio_structured_output_and_documented_tools(self):
        requests = [{"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "module_get", "arguments": {"project": str(self.root), "id": "feature"}}}]
        result = subprocess.run([sys.executable, "-m", "vervision", "mcp"], input="\n".join(map(json.dumps, requests)) + "\n",
                                capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(lines[0]["result"]["tools"]), len(TOOLS))
        response = lines[1]["result"]
        self.assertEqual(response["structuredContent"]["id"], "feature")
        self.assertNotIn("body", response["structuredContent"])
        self.assertLess(len(response["content"][0]["text"]), 80)


if __name__ == "__main__":
    unittest.main()
