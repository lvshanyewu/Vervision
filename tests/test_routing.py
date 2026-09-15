import json
import shutil
import unittest
from pathlib import Path

import test_core
from vervision import core
from vervision.formats import read_sections
from vervision.mcp_server import call_tool, TOOLS


class RoutingTests(unittest.TestCase):
    setUp = test_core.CoreTests.setUp
    tearDown = test_core.CoreTests.tearDown

    def read(self, **args):
        return call_tool("module_get", {"project": str(self.root), "id": "feature", **args})

    def test_ui_does_not_match_build_or_guidelines(self):
        core.save_module(self.root, {"id": "cloud-drive", "summary": "Build guidelines",
                                    "sources": ["src/feature.py"]})
        core.save_module(self.root, {"id": "ui", "summary": "UI components",
                                    "sources": ["src/feature.py"]})
        result = core.resolve_task(self.root, "UI")
        self.assertEqual([m["id"] for m in result["matches"]], ["ui"])

    def test_exact_path_beats_broad_metadata_and_body(self):
        core.save_module(self.root, {"id": "broad", "title": "UI release", "summary": "UI release",
                                    "aliases": ["UI release"], "tags": ["UI", "release"],
                                    "sources": ["src/**"], "body": "feature.py"})
        for task in ('UI release: `src/feature.py`', '修改“feature.py”', r'UI src\feature.py'):
            with self.subTest(task=task):
                matches = core.resolve_task(self.root, task)["matches"]
                self.assertEqual([m["id"] for m in matches], ["feature"])
                self.assertIn("src/feature.py", matches[0]["matched_paths"])
        self.assertEqual(core.search(self.root, "src/feature.py")[0]["id"], "feature")

    def test_specific_path_does_not_match_other_directory_same_basename(self):
        core.save_module(self.root, {"id": "other", "summary": "other",
                                    "sources": ["elsewhere/feature.py"]})
        matches = core.resolve_task(self.root, "src/feature.py")["matches"]
        self.assertEqual([m["id"] for m in matches], ["feature"])

    def test_zen_routes_to_single_source_without_loading_original(self):
        repo = Path(__file__).resolve().parents[1]
        shutil.copyfile(repo / "ZEN.md", self.root / "ZEN.md")
        shutil.copyfile(repo / ".handoff/modules/design-philosophy.md",
                        self.root / ".handoff/modules/design-philosophy.md")
        for task in ("ZEN.md", "architecture", "context routing", "retrieval", "MCP", "metadata",
                     "agent autonomy", "token efficiency", "product boundaries", "元数据设计", "产品边界"):
            with self.subTest(task=task):
                resolved = call_tool("resolve", {"project": str(self.root), "task": task})
                self.assertIn("design-philosophy", [m["id"] for m in resolved["matches"]])
                action = resolved["next_actions"][0]
                read = call_tool(action["tool"], action["arguments"])
                pointer = next(m for m in read["results"] if m["id"] == "design-philosophy")
                self.assertEqual(pointer["sources"], ["ZEN.md"])
                if "body" in pointer:
                    self.assertIn("sections", action["arguments"])
                self.assertNotIn("Route precisely. Reveal progressively.", json.dumps(read))
        ordinary = core.resolve_task(self.root, "修改 src/feature.py 格式")
        self.assertNotIn("design-philosophy", [m["id"] for m in ordinary["matches"]])
        self.assertEqual(ordinary["dependency_summaries"], [])

    def test_full_module_does_not_embed_historical_instructions(self):
        core.save_continuation(self.root, {"id": "old", "module_id": "feature", "status": "done",
                                          "next_step": "Obsolete instruction", "body": "Use an obsolete model"})
        for args in ({}, {"full": True}):
            result = self.read(**args)
            if args.get("full"):
                self.assertEqual(result["continuations"][0]["id"], "old")
            else:
                self.assertEqual(result["continuations"], [])
            self.assertNotIn("Obsolete instruction", json.dumps(result))
            self.assertNotIn("Use an obsolete model", json.dumps(result))
        old = call_tool("continuation_get", {"project": str(self.root), "id": "old", "full": True})
        self.assertIn("Use an obsolete model", old["body"])

    def test_section_read_uses_outline_and_preserves_fenced_code(self):
        body = "Preamble\n# Current\nKeep\n## Child\n```md\n# Fake\n```\n# Release\nOnly release\n"
        core.save_module(self.root, {"id": "feature", "body": body}, core.get_module(self.root, "feature").revision)
        outline = self.read()
        self.assertEqual(outline["sections"], ["Current", "Child", "Release"])
        selected = self.read(sections=["Current", "Child"])
        self.assertEqual(selected["body"], "# Current\nKeep\n## Child\n```md\n# Fake\n```\n")
        self.assertEqual(selected["revision"], outline["revision"])
        self.assertNotIn("body", outline)
        for sections in (["Fake"], ["Missing"]):
            with self.assertRaisesRegex(ValueError, "exactly one"):
                self.read(sections=sections)
        with self.assertRaisesRegex(ValueError, "not both"):
            self.read(sections=["Current"], full=True)

    def test_section_read_rejects_duplicates_and_batch_reports_errors(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            read_sections("# Same\nA\n# Same\nB", ["Same"])
        result = call_tool("module_get_many", {"project": str(self.root), "ids": ["feature", "missing"],
                                               "sections": ["Feature"]})
        self.assertIn("Keep IDs stable", result["results"][0]["body"])
        self.assertIn("error", result["results"][1])

    def test_changed_sources_tracks_added_removed_modified_and_reindex(self):
        doc = core.get_module(self.root, "feature")
        core.save_module(self.root, {"id": "feature", "sources": ["src/**"]}, doc.revision)
        removed = self.root / "src/removed.py"
        removed.write_text("old", encoding="utf-8")
        core.verify_module(self.root, "feature")
        removed.unlink()
        (self.root / "src/feature.py").write_text("changed", encoding="utf-8")
        (self.root / "src/added.py").write_text("new", encoding="utf-8")
        core.rebuild_index(self.root)
        status = call_tool("module_status", {"project": str(self.root), "module_id": "feature"})
        self.assertEqual(status["changed_sources"], [
            {"path": "src/added.py", "change": "added"},
            {"path": "src/feature.py", "change": "modified"},
            {"path": "src/removed.py", "change": "removed"}])
        self.assertEqual(status["state"], "STALE")
        core.verify_module(self.root, "feature")
        self.assertEqual(core.module_status(self.root, core.get_module(self.root, "feature"))["changed_sources"], [])

    def test_changed_sources_unknown_without_per_file_baseline(self):
        doc = core.get_module(self.root, "feature")
        self.assertIsNone(core.module_status(self.root, doc)["changed_sources"])
        core.verify_module(self.root, "feature")
        with core._verification_db() as db:
            baseline = core.verification_baseline(self.root, doc)
            baseline.pop("source_fingerprints")
            db.execute("UPDATE verification SET value=?", (json.dumps(baseline),))
        status = core.module_status(self.root, doc)
        self.assertEqual(status["state"], "FRESH")
        self.assertIsNone(status["changed_sources"])
        self.assertTrue(core.verify_module(self.root, "feature")["verification_changed"])
        self.assertFalse(core.verify_module(self.root, "feature")["verification_changed"])

    def test_continuation_conflict_returns_revision_and_describes_contract(self):
        args = {"project": str(self.root), "id": "task", "module_id": "feature", "next_step": "Review"}
        saved = call_tool("continuation_save", args)
        with self.assertRaises(core.RevisionConflict) as caught:
            call_tool("continuation_save", {"project": str(self.root), "id": "task", "status": "done", "expected_revision": "stale"})
        self.assertEqual(caught.exception.details["revision"], saved["revision"])
        description = next(t["description"] for t in TOOLS if t["name"] == "continuation_save")
        self.assertIn("Optional expected_revision", description)

    def set_body(self, body):
        core.save_module(self.root, {"id": "feature", "body": body}, core.get_module(self.root, "feature").revision)

    def test_search_prefers_current_section_and_history_is_explicit(self):
        self.set_body("# History\n## Old\nRouting retired policy\n# Current\nRouting active policy\n# Other\nUnrelated notes\n")
        core.save_continuation(self.root, {"id": "old", "title": "Routing", "module_id": "feature", "status": "done", "next_step": "Routing retired"})
        result = call_tool("search", {"project": str(self.root), "query": "routing"})
        self.assertEqual([r["id"] for r in result["results"]], ["feature"])
        hit = result["results"][0]
        self.assertEqual(hit["matched_section"], "Current")
        self.assertIn("active", hit["match_reason"]["snippet"])
        read = call_tool(hit["next_action"]["tool"], hit["next_action"]["arguments"])
        self.assertNotIn("retired", read["body"])
        self.assertNotIn("Unrelated", read["body"])
        expanded = call_tool("search", {"project": str(self.root), "query": "routing", "include_history": True})
        self.assertIn("old", [r["id"] for r in expanded["results"]])
        self.assertIn("retired", self.read(full=True)["body"])

    def test_search_snippet_and_ranking_use_same_filtered_lines(self):
        self.set_body("# Current\nRouting 1.0.3 old release\nRouting current policy\n")
        hit = core.search(self.root, "routing")[0]
        self.assertEqual(hit["match_reason"]["snippet"], "Routing current policy")
        self.assertEqual(core.search(self.root, "retiredtoken"), [])
        self.set_body("# Current\nretiredtoken 1.0.3 release\n")
        self.assertEqual(core.search(self.root, "retiredtoken"), [])
        self.assertEqual(core.search(self.root, "retiredtoken", include_history=True)[0]["id"], "feature")

    def test_search_does_not_propose_ambiguous_or_parent_sections(self):
        for body in ("# Same\nRouting\n# Same\nRouting\n", "# Routing\nRouting\n## History\nOld\n"):
            self.set_body(body)
            hit = core.search(self.root, "routing")[0]
            self.assertNotIn("sections", hit["next_action"]["arguments"])
            self.assertNotIn("matched_section", hit)

    def test_search_limit_and_more_are_shared_with_cli(self):
        for i in range(7):
            core.save_module(self.root, {"id": f"item-{i}", "summary": "needle", "sources": ["src/feature.py"]})
        args = {"project": str(self.root), "query": "needle"}
        page = call_tool("search", args)
        self.assertEqual(len(page["results"]), 5)
        self.assertTrue(page["has_more"])
        self.assertFalse(call_tool("search", {**args, "limit": 10})["has_more"])
        for limit in (0, 51, True, 1.5):
            with self.assertRaises(ValueError):
                call_tool("search", {**args, "limit": limit})
        import subprocess, sys
        result = subprocess.run([sys.executable, "-m", "vervision", "search", "needle", "--project", str(self.root), "--limit", "2"], capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)["results"]), 2)

    def test_resolve_groups_matching_sections_without_loading_bodies(self):
        self.set_body("# Policy\nRouting policy\n# Other\nUnrelated\n")
        resolved = call_tool("resolve", {"project": str(self.root), "task": "feature routing"})
        self.assertNotIn("body", resolved["matches"][0])
        action = resolved["next_actions"][0]
        self.assertEqual(action["arguments"]["sections"], ["Policy"])
        read = call_tool(action["tool"], action["arguments"])
        self.assertNotIn("Unrelated", read["results"][0]["body"])

    def test_review_candidates_are_bounded_explicit_and_do_not_verify(self):
        self.set_body("# Other\nelsewhere/feature.py\n# History\nfeature.py old\n" + "".join(f"# Current {i}\nSee `src/feature.py`.\n" for i in range(7)))
        core.verify_module(self.root, "feature")
        (self.root / "src/feature.py").write_text("VALUE = 2\n", encoding="utf-8")
        doc = core.get_module(self.root, "feature")
        before = doc.path.read_bytes()
        baseline = core.verification_baseline(self.root, doc)
        status = core.module_status(self.root, doc)
        self.assertEqual(status["change_summary"], {"added": 0, "modified": 1, "removed": 0})
        self.assertNotIn("review_candidates", status)
        expanded = call_tool("module_status", {"project": str(self.root), "module_id": "feature", "review": True})
        review = expanded["review_candidates"]
        self.assertTrue(review["baseline_known"])
        self.assertEqual(len(review["candidates"]), 5)
        self.assertEqual(review["omitted_count"], 2)
        self.assertIn("unverified", review["candidates"][0]["reason"])
        self.assertEqual(review["candidates"][0]["heading"], "Current 0")
        self.assertEqual(doc.path.read_bytes(), before)
        self.assertEqual(core.verification_baseline(self.root, doc), baseline)
        self.assertEqual(expanded["state"], "STALE")

    def test_review_distinguishes_unknown_no_change_and_no_reference(self):
        doc = core.get_module(self.root, "feature")
        unknown = core.module_status(self.root, doc, review=True)
        self.assertIsNone(unknown["change_summary"])
        self.assertFalse(unknown["review_candidates"]["baseline_known"])
        core.verify_module(self.root, "feature")
        fresh = core.module_status(self.root, doc, review=True)
        self.assertEqual(fresh["review_candidates"]["candidates"], [])
        self.assertEqual(sum(fresh["change_summary"].values()), 0)
        (self.root / "src/feature.py").unlink()
        stale = core.module_status(self.root, doc, review=True)
        self.assertEqual(stale["change_summary"]["removed"], 1)
        self.assertTrue(stale["review_candidates"]["baseline_known"])
        self.assertEqual(stale["review_candidates"]["candidates"], [])


if __name__ == "__main__":
    unittest.main()
