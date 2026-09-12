---
schema_version: 1
type: "module"
id: "context-router"
title: "上下文路由与交接核心"
summary: "定位项目、按任务检索交接、核对来源新鲜度，并通过统一接口供 Agent 和本地 WebUI 使用。"
aliases: ["Vervision MCP", "项目发现", "handoff core"]
tags: ["python", "mcp", "context-router"]
sources: ["vervision/**", "tests/**", "templates/**", "README.md", "FORMAT.md", "pyproject.toml", "scripts/**", "start-vervision.cmd", "启动 Vervision.cmd"]
dependencies: []
related_modules: []
business_rules: ["resolve 先定位项目，再返回最多三份强相关模块和必要依赖摘要；默认 concise，detailed 提供完整诊断。", "FRESH 仅说明已记录来源摘要与当前来源摘要一致；文档语义核验由独立状态表达。", "更新已有模块必须携带 expected_revision；省略字段保留，显式空数组清空。", "search 命中的任意文档类型必须能由 handoff_get 读取。"]
invariants: ["Markdown 是主数据，SQLite 只能作为可重建索引。", "module_verify 只能在 Agent 完成语义核对后调用。", "不得把密钥、个人数据或生产数据库写入交接与索引。", "项目证据不唯一时返回候选，不静默选择。"]
consumers: ["Codex 等 MCP Agent", "handoff/vervision CLI", "本地 WebUI", "使用 .handoff 的其他个人项目"]
updated_at: "2026-09-12T10:11:13+08:00"
verified_digest: "31ee38b5377e58f0d570e1451da3f5d911dc67a367529b85c4abdc8311761734"
verified_at: "2026-09-12T10:11:13+08:00"
verified_document_digest: "5c009bbeefd36ad45f55ce0970684a8e03d0765f6f005ee485b73ab002da3e70"
---

# 当前实现

`core.py` 管理项目登记、候选发现与评分、文档读取、加权搜索、来源摘要、来源状态、文档语义核验状态、模块写入和 continuation。项目选择综合 MCP 工作区、显式 `workspace`、当前目录及父目录、相邻目录、登记表和任务相关度；只有唯一或分数明显领先时才自动选择。

`mcp_server.py` 暴露七个工具。Agent 从 `resolve` 开始；默认 concise 响应保留必要约束、状态和一份下一步参数，`detail=detailed` 返回完整诊断。一次 resolve 共享解析后的文档、受限来源清单和文件摘要，相同依赖只生成一份摘要。`search` 返回命中字段和短片段；`handoff_get` 统一读取 overview、module、continuation。支持 MCP Roots 的客户端初始化后通过 `roots/list` 提供工作区。

WebUI 和 CLI 复用同一 core。模块更新采用乐观并发控制：省略字段保留、显式空数组清空、未知扩展字段保留；无实质变化时不重写文件。所有写操作返回写后 revision。安装包由 `scripts/build-release.ps1` 生成。

来源状态只回答关联源码相对最近基线是否变化。人工核验还会记录排除工具字段的文档语义指纹；正文或业务字段后来改变时显示 PENDING，旧文档没有该指纹时显示 UNKNOWN_LEGACY。WebUI 分开展示来源状态和交接语义核验，并明确前者不代表线上配置或运行环境有效。

WebUI 项目列表会把所有模块的 `sources` 合并为一次受限文件清单，只扫描这些路径前缀，再为各模块计算状态；模块详情优先按约定文件名直接读取，并复用项目列表刚计算的状态。前端缓存已经访问过的项目列表，同时后台刷新，并用请求令牌阻止旧项目或旧卡片响应覆盖当前界面。

根目录的 `启动 Vervision.cmd` 和 `start-vervision.cmd` 调用 `scripts/start-vervision.ps1`。启动脚本先检查 8765 上是否已有 Vervision，再依次查找已安装程序、解压包 EXE、最新版本化 EXE、旧版 EXE和源码 Python 入口；服务就绪后才打开浏览器，失败信息写入 `%LOCALAPPDATA%\Vervision\logs`。

## 验证与回退

- 单元测试覆盖部分更新与冲突、无变化保存、双维核验状态、共享来源扫描、紧凑/详细响应、统一读取、跨项目任务选择和 MCP file roots 解析。
- 修改路由协议后运行 `python -m unittest discover -s tests -v`，再执行一次真实 MCP JSON-RPC 冒烟测试。
- 回退以 Git 提交为单位；项目 `.handoff` 文件和本地登记表无需随程序回退。
