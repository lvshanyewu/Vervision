---
schema_version: 1
type: "overview"
id: "vervision"
title: "Vervision"
summary: "本地运行的个人项目交接与上下文路由工具，通过 Markdown、CLI、WebUI 和 MCP 服务多 Agent、多会话开发。"
architecture_summary: "项目 Markdown（含登记的外部原文）是事实源；core 负责发现、搜索、Freshness 与写入，MCP/CLI/WebUI 是轻量入口，SQLite 仅作可重建索引与本机核验记录。"
aliases: ["handoff", "上下文管理", "项目记忆"]
tags: ["python", "mcp", "local-first"]
updated_at: "2026-09-10"
---

# Overview

Vervision 面向个人长期项目，用很少的调用把 Agent 路由到正确项目、相关交接与真实源码。它不承担团队权限、分支管理或远程同步。

## 模块导航

- `context-router`：项目发现、统一读取、搜索、Freshness、任务接续，以及 MCP/CLI/WebUI 接口。
- `design-philosophy`：重大设计决策时导航到根目录 `ZEN.md` 唯一原文；不作为普通任务的默认依赖。

## 公共约束

- `.handoff` 中的 Markdown 是可迁移的主数据，SQLite 索引必须可随时删除并重建。
- `FRESH` 只表示来源文件自语义核验后未变化，不能代表线上状态或自动证明文档正确。
- 保持本地优先、标准库运行时和轻量单人工作流。
