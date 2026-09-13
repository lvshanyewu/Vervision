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
updated_at: "2026-09-12T19:55:45+08:00"
verified_digest: "31ee38b5377e58f0d570e1451da3f5d911dc67a367529b85c4abdc8311761734"
verified_at: "2026-09-12T10:11:13+08:00"
verified_document_digest: "5c009bbeefd36ad45f55ce0970684a8e03d0765f6f005ee485b73ab002da3e70"
---

# 当前实现

`core.py` 管理项目登记、文档检索、来源指纹、独立语义核验、模块写入和 continuation。显式项目优先；其次按工作区包含关系定位最近项目。多个工作区或无包含关系的多候选不按任务分数或唯一模块 ID 自动选择。检索标题、aliases、tags、sources、dependencies 权重高于正文，版本流水行过滤，正文得分封顶。

`mcp_server.py` 的 resolve 返回仅当前 MCP 会话有效的 scope_id 和模块 revision。后续调用复用 scope；与显式项目或工作区冲突时拒绝。默认 structuredContent/concise，full=true 返回正文；module_get、overview_get、continuation_get 为正式接口，handoff_get 保留兼容。resolve.next_actions 使用 module_get_many。

模块元数据使用部分更新；module_patch 支持唯一 ATX 标题内容和 fields。批量 module_save_many 每项独立保存并可 verify=true，采用明确的部分成功报告，不实现跨文件事务。module_save_and_verify 在同一项目写锁下完成保存和核验，核验失败保留保存并返回最终 revision 与错误。locking.py 提供跨进程写锁，单文件写入采用临时文件替换；revision 固定于文档读取快照。

verify 将源码指纹、语义指纹、verified_at 写入本机 SQLite verification 表，不改写 Markdown。重复核验幂等，旧文件基线兼容，本机新基线优先。reindex 保留核验表；换机器或删除索引后需重新核验。source_freshness 只说明源码变化，document_verification 只记录 Agent/人工语义核对，external_checks 默认 NOT_CHECKED。工具不会核对正文中的测试数量、哈希或服务可用性。

临时进度写 continuation，更新需 expected_revision，省略字段保留，可只改 status=done。external_checks 保存 Agent 提供的 service/status/evidence/checked_at。版本历史写 CHANGELOG 或发布记录；长期规则改变时才 patch 模块，不自动搬运临时正文。

WebUI、CLI 复用 core；WebUI 展示源码新鲜度、独立文档核验和外部状态边界，核验后清除对应状态缓存。根目录启动脚本调用 scripts/start-vervision.ps1。安装包由 scripts/build-release.ps1 根据包版本生成。

## 验证与回退

- 运行 python -m unittest discover -s tests -v、真实 MCP JSON-RPC 冒烟及项目 validate。
- scripts/benchmark-mcp.py 对指定 Git 旧版本测量隔离双模块维护调用数与响应字符数，不作为 token 计费估算。
- 回退以 Git 提交为单位；Markdown 仍是长期知识事实源，本机核验记录可以丢弃后重新核对。
