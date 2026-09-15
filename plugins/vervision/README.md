# Vervision Codex plugin

This is a thin local plugin: one Skill and the existing `python -m vervision mcp`
stdio server. It does not bundle a second Core, upload project data, or require
WebUI to run.

## Prerequisite and installation

Install Vervision 0.5.0 or newer into Python 3.10+ first, for example from this repository:

```powershell
python -m pip install -e D:\vervision
```

The plugin's `.mcp.json` uses that Python on PATH. For a stable Windows setup,
replace `command` with the absolute interpreter path. Alternatively point
`command` at the installed `vervision.exe` and use `args: ["mcp"]`.
Do not put PowerShell environment-variable expressions into a JSON command path.

Use Codex's plugin-creator to register this folder in your personal marketplace,
then install Vervision from the local plugin directory. Start a new task after
installation to pick up its Skill and tools. If another Vervision MCP connection
is already enabled, use one connection for the task to avoid duplicate tools.

The local development copy created for this checkout uses an absolute Python
interpreter and `PYTHONPATH` pointing to the checkout; it runs the current source
even after Codex copies the plugin into its cache. The generic package here has
no machine-specific paths. Moving a local checkout requires updating that local
connection and reinstalling the plugin.

## Compatibility and official references

Checked 2026-09-15: the [official packaging documentation](https://developers.openai.com/plugins/build/plugins)
still supports plugin-creator's `.codex-plugin/plugin.json` and `.mcp.json`
compatibility layout. The newer portable manifest is optional. This package
targets local Codex; installing it on a web/cloud surface does not provision
Python or expose Windows project files there. No remote bridge is included.

CLI, WebUI and other MCP clients continue using the same independent Vervision
installation. An old installed EXE must be upgraded to receive Core fixes.
