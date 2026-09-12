import tempfile
import unittest
from pathlib import Path

import vervision.core as core
from vervision.core import (
    get_document, get_module, import_bundle, init_project, module_status, resolve_task,
    save_module, search, select_project, source_inventory, validate_project, verify_module,
)
from vervision.mcp_server import _accept_roots, call_tool, WORKSPACE_ROOTS


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_registry, self.old_index = core.REGISTRY, core.INDEX
        core.APP_HOME = self.root / ".app-data"
        core.REGISTRY = core.APP_HOME / "projects.json"
        core.INDEX = core.APP_HOME / "index.sqlite3"
        init_project(self.root, "test-project", "Test Project")
        (self.root / "src").mkdir()
        (self.root / "src" / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
        save_module(self.root, {
            "id": "feature", "title": "Feature", "summary": "作文 review feature",
            "aliases": ["essay"], "tags": ["python"], "sources": ["src/feature.py"],
            "dependencies": [], "related_modules": [], "body": "# Feature\n\nKeep IDs stable.",
        }, "new")

    def tearDown(self):
        core.REGISTRY, core.INDEX = self.old_registry, self.old_index
        self.temp.cleanup()

    def test_freshness_loop(self):
        doc = get_module(self.root, "feature")
        self.assertEqual(module_status(self.root, doc)["state"], "UNVERIFIED")
        verify_module(self.root, "feature")
        self.assertEqual(module_status(self.root, get_module(self.root, "feature"))["state"], "FRESH")
        (self.root / "src" / "feature.py").write_text("VALUE = 2\n", encoding="utf-8")
        self.assertEqual(module_status(self.root, get_module(self.root, "feature"))["state"], "STALE")

    def test_partial_update_preserves_omitted_and_extension_fields(self):
        path = self.root / ".handoff" / "modules" / "feature.md"
        text = path.read_text(encoding="utf-8").replace("tags: [\"python\"]", "tags: [\"python\"]\nextension_note: \"keep me\"")
        path.write_text(text, encoding="utf-8")
        before = get_module(self.root, "feature")
        result = save_module(self.root, {"id": "feature", "body": "# Updated"}, before.revision)
        after = get_module(self.root, "feature")
        self.assertTrue(result["changed"])
        self.assertEqual(after.meta["sources"], ["src/feature.py"])
        self.assertEqual(after.meta["extension_note"], "keep me")
        self.assertEqual(after.body, "# Updated\n")

    def test_explicit_empty_list_clears_field(self):
        before = get_module(self.root, "feature")
        save_module(self.root, {"id": "feature", "aliases": []}, before.revision)
        self.assertEqual(get_module(self.root, "feature").meta["aliases"], [])

    def test_existing_module_requires_revision_and_new_conflicts_cleanly(self):
        with self.assertRaisesRegex(RuntimeError, "expected_revision is required"):
            save_module(self.root, {"id": "feature", "body": "overwrite"})
        with self.assertRaises(FileExistsError):
            save_module(self.root, {"id": "feature"}, "new")

    def test_noop_save_is_stable_and_verify_returns_written_revision(self):
        verified = verify_module(self.root, "feature")
        self.assertEqual(verified["revision"], get_module(self.root, "feature").revision)
        before = get_module(self.root, "feature")
        result = save_module(self.root, {"id": "feature"}, before.revision)
        after = get_module(self.root, "feature")
        self.assertFalse(result["changed"])
        self.assertEqual(result["revision"], before.revision)
        self.assertEqual(after.meta["verified_digest"], before.meta["verified_digest"])

    def test_markdown_trailing_spaces_are_preserved(self):
        before = get_module(self.root, "feature")
        save_module(self.root, {"id": "feature", "body": "line with break  "}, before.revision)
        self.assertIn("line with break  \n", (self.root / ".handoff" / "modules" / "feature.md").read_text(encoding="utf-8"))

    def test_document_verification_detects_manual_body_edit(self):
        verify_module(self.root, "feature")
        verified = module_status(self.root, get_module(self.root, "feature"))
        self.assertEqual(verified["document_verification"]["state"], "VERIFIED")
        path = self.root / ".handoff" / "modules" / "feature.md"
        path.write_text(path.read_text(encoding="utf-8") + "manual edit\n", encoding="utf-8")
        changed = module_status(self.root, get_module(self.root, "feature"))
        self.assertEqual(changed["state"], "FRESH")
        self.assertEqual(changed["document_verification"]["state"], "PENDING")

    def test_tool_timestamps_do_not_invalidate_document_verification(self):
        verify_module(self.root, "feature")
        path = self.root / ".handoff" / "modules" / "feature.md"
        doc = get_module(self.root, "feature")
        doc.meta["updated_at"] = "2099-01-01T00:00:00+00:00"
        path.write_text(core.dump_document(doc.meta, doc.body), encoding="utf-8")
        self.assertEqual(module_status(self.root, get_module(self.root, "feature"))["document_verification"]["state"], "VERIFIED")

    def test_legacy_verified_document_is_reported_honestly(self):
        verify_module(self.root, "feature")
        path = self.root / ".handoff" / "modules" / "feature.md"
        doc = get_module(self.root, "feature")
        doc.meta.pop("verified_document_digest")
        path.write_text(core.dump_document(doc.meta, doc.body), encoding="utf-8")
        status = module_status(self.root, get_module(self.root, "feature"))
        self.assertEqual(status["state"], "FRESH")
        self.assertEqual(status["document_verification"]["state"], "UNKNOWN_LEGACY")

    def test_shared_source_inventory_keeps_freshness_result(self):
        doc = get_module(self.root, "feature")
        direct = module_status(self.root, doc)
        batched = module_status(self.root, doc, source_inventory(self.root, doc.meta["sources"]))
        self.assertEqual(batched, direct)

    def test_rebuilt_bounded_inventory_detects_source_add_and_delete(self):
        before = get_module(self.root, "feature")
        save_module(self.root, {"id": "feature", "sources": ["src/**"]}, before.revision)
        verify_module(self.root, "feature")
        self.assertEqual(resolve_task(self.root, "作文")["matches"][0]["freshness"]["state"], "FRESH")
        extra = self.root / "src" / "extra.py"
        extra.write_text("EXTRA = 1\n", encoding="utf-8")
        self.assertEqual(resolve_task(self.root, "作文")["matches"][0]["freshness"]["state"], "STALE")
        verify_module(self.root, "feature")
        extra.unlink()
        self.assertEqual(resolve_task(self.root, "作文")["matches"][0]["freshness"]["state"], "STALE")

    def test_resolve(self):
        result = resolve_task(self.root, "优化作文 essay")
        self.assertEqual(result["matches"][0]["id"], "feature")

    def test_validation(self):
        self.assertEqual(validate_project(self.root), [])

    def test_search_result_can_be_read_through_unified_reader(self):
        result = next(item for item in search(self.root, "overview") if item["type"] == "overview")
        self.assertEqual(result["next_action"]["tool"], "handoff_get")
        doc = get_document(self.root, result["id"], "overview")
        self.assertEqual(doc.meta["type"], "overview")
        value = call_tool("handoff_get", {"project": str(self.root), "id": result["id"]})
        self.assertEqual(value["type"], "overview")

    def test_task_relevance_can_select_registered_adjacent_project(self):
        other = self.root.parent / f"{self.root.name}-vervision"
        try:
            init_project(other, "vervision-test", "Vervision Test")
            (other / "router.py").write_text("# MCP project router\n", encoding="utf-8")
            save_module(other, {"id": "router", "title": "Vervision MCP router",
                        "summary": "Resolve the correct project", "sources": ["router.py"], "body": "# Router"}, "new")
            selected = select_project(task="repair Vervision MCP router", workspaces=[self.root])
            self.assertEqual(Path(selected["selected"]), other)
        finally:
            import shutil
            shutil.rmtree(other, ignore_errors=True)

    def test_resolve_includes_architecture_constraints_and_exact_next_call(self):
        overview = self.root / ".handoff" / "overview.md"
        text = overview.read_text(encoding="utf-8").replace(
            'summary: "Project handoff overview."',
            'summary: "Project handoff overview."\narchitecture_summary: "CLI routes to a local core."')
        overview.write_text(text, encoding="utf-8")
        save_module(self.root, {"id": "foundation", "title": "Foundation", "summary": "Shared data contract",
                    "sources": ["src/feature.py"], "body": "# Foundation"}, "new")
        save_module(self.root, {"id": "feature", "title": "Feature", "summary": "作文 review feature",
                    "sources": ["src/feature.py"], "dependencies": ["foundation"],
                    "business_rules": ["Count accepted essays only"],
                    "invariants": ["Keep IDs stable"], "consumers": ["mobile app"], "body": "# Feature"},
                    get_module(self.root, "feature").revision)
        result = resolve_task(self.root, "作文", detail="detailed")
        self.assertEqual(result["project_context"]["architecture"], "CLI routes to a local core.")
        self.assertEqual(result["matches"][0]["business_rules"], ["Count accepted essays only"])
        self.assertEqual(result["matches"][0]["dependencies"], ["foundation"])
        self.assertEqual(result["dependency_summaries"][0]["id"], "foundation")
        self.assertEqual(result["next_actions"][0]["tool"], "handoff_get")

    def test_resolve_uses_one_inventory_and_reuses_file_digests(self):
        save_module(self.root, {"id": "foundation", "title": "Foundation", "summary": "Shared",
                    "sources": ["src/**"], "body": "# Foundation"}, "new")
        before = get_module(self.root, "feature")
        save_module(self.root, {"id": "feature", "dependencies": ["foundation"]}, before.revision)
        inventory_calls, read_paths = 0, []
        original_inventory, original_read_bytes = core.source_inventory, Path.read_bytes

        def counted_inventory(root, patterns=None):
            nonlocal inventory_calls
            inventory_calls += 1
            return original_inventory(root, patterns)

        def counted_read_bytes(path):
            read_paths.append(path)
            return original_read_bytes(path)

        core.source_inventory, Path.read_bytes = counted_inventory, counted_read_bytes
        try:
            result = resolve_task(self.root, "作文")
        finally:
            core.source_inventory, Path.read_bytes = original_inventory, original_read_bytes
        self.assertEqual(inventory_calls, 1)
        self.assertEqual(read_paths.count(self.root / "src" / "feature.py"), 1)
        self.assertEqual(result["matches"][0]["dependencies"], ["foundation"])

    def test_concise_resolve_has_one_next_action_and_detailed_has_diagnostics(self):
        concise = resolve_task(self.root, "作文")
        self.assertEqual(len(concise["next_actions"]), 1)
        self.assertNotIn("next_actions", concise["matches"][0])
        self.assertNotIn("score", concise["matches"][0])
        self.assertIn("business_rules", concise["matches"][0])
        detailed = resolve_task(self.root, "作文", detail="detailed")
        self.assertIn("score", detailed["matches"][0])
        self.assertIn("resolved_source_sample", detailed["matches"][0]["freshness"])

    def test_search_explains_match(self):
        result = search(self.root, "essay")[0]
        self.assertIn("aliases", result["match_reason"]["fields"])

    def test_ambiguous_discovery_returns_candidates(self):
        choices = self.root / "choices"
        first, second, workspace = choices / "project-a", choices / "project-b", choices / "notes"
        init_project(first, "project-a", "Project A")
        init_project(second, "project-b", "Project B")
        workspace.mkdir()
        core._save_registry({"project-a": str(first), "project-b": str(second)})
        selection = select_project(workspaces=[workspace])
        self.assertEqual(selection["status"], "ambiguous")
        self.assertTrue({"project-a", "project-b"}.issubset({item["id"] for item in selection["candidates"]}))

    def test_mcp_file_roots_are_decoded(self):
        _accept_roots({"roots": [{"uri": self.root.as_uri()}]})
        self.assertEqual(WORKSPACE_ROOTS, [self.root.resolve()])
        WORKSPACE_ROOTS.clear()


if __name__ == "__main__":
    unittest.main()
