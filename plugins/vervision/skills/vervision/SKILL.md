---
name: vervision
description: Find relevant local project knowledge and maintain handoff modules or temporary continuation progress with Vervision. Use when project context in .handoff would help the current task or the user asks to use Vervision.
---

# Vervision

Vervision routes to evidence; the agent reasons. Project Markdown and actual source
remain inspectable. Routing suggestions are candidates, not mandatory work.

- When useful, call `resolve` with the task and explicit project/workspace path.
  Reuse its session `scope_id`; resolve again after a server restart.
- Start with metadata and headings. Read relevant `sections`, or source files,
  only as needed. Use `full=true` when the whole document is actually necessary.
  Enough evidence already available means another read can be skipped.
- `search` returns five results by default; `has_more` signals more matches.
  Narrow the query or increase `limit` (up to 50). `resolve`/`search` may suggest
  a matching unique leaf section in `next_actions`/`next_action`; use it when
  useful. A suggested section is lexical evidence, not a semantic conclusion.
- Historical continuations and release records are past observations, not current
  instructions. Default search excludes done progress and explicit history
  sections; use `include_history=true` when needed. Exact known continuation IDs
  remain directly readable. `full=true` returns unfiltered original text.
- `STALE` means registered source changed, not that knowledge is wrong. Inspect
  `module_status.changed_sources` to narrow review. `null` means the per-file
  baseline is unknown. `change_summary` counts source additions/modifications/
  removals. With `review=true`, `module_status` returns up to five candidate
  locations in that module which directly mention changed paths or filenames,
  plus omitted counts. These may be incomplete or unrelated; no match does not
  prove no impact. Changes can also come from editing `sources`. No baseline
  code diff is available; Git diffs have their own comparison base. `FRESH` is
  not proof of semantic correctness.
- Save temporary progress through `continuation_save`, sending only changed
  fields. A simple status update needs no prior read. Omitted fields are preserved;
  supplied fields replace current values under a write lock. If a change depends
  on a previously read version (especially rewriting its body), pass that
  `expected_revision`. Use `expected_revision="new"` for create-only intent.
  On a conflict, inspect affected content and reconsider before retrying.
- For stable knowledge, use `module_patch` with the observed revision, or
  `module_save_many` for independent module changes. Only verify after personally
  checking meaning against source. Never auto-promote temporary progress or
  rewrite knowledge merely because freshness changed.

Do not impose initialization, full handoff reads, extra metadata, or verification
ceremonies on tasks that do not need them. Respect the project's own rules.
