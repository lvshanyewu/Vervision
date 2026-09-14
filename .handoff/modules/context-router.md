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
updated_at: "2026-09-14T09:17:27+08:00"
verified_digest: "31ee38b5377e58f0d570e1451da3f5d911dc67a367529b85c4abdc8311761734"
verified_at: "2026-09-12T10:11:13+08:00"
verified_document_digest: "5c009bbeefd36ad45f55ce0970684a8e03d0765f6f005ee485b73ab002da3e70"
---

# 当前实现

`core.py` 管理项目登记、文档检索、来源指纹、独立语义核验、模块写入和 continuation。显式项目优先；其次按工作区包含关系定位最近项目。多候选不按任务分数或唯一模块 ID 自动选择。检索标题、aliases、tags、sources、dependencies 权重高于正文，正文得分封顶并过滤版本流水。英文关键词使用词边界；精确登记的来源或文档路径/文件名优先，resolve 有精确模块命中时不再扩展泛关键词候选。

`mcp_server.py` 的 resolve 返回仅当前 MCP 会话有效的 scope_id 和模块 revision。后续调用复用 scope；与显式项目或工作区冲突时拒绝。默认 structuredContent/concise，resolve/search 的下一步先返回 metadata、来源路径和章节标题。读取接口支持 sections 选择唯一 ATX 标题及子章节，或 full=true 显式读取该文档全文；两者互斥。模块只附带 continuation 的 id/title/status，历史正文通过 continuation_get 显式读取。正式类型读取保留，handoff_get 兼容。

模块元数据使用部分更新；module_patch 与章节读取共用 formats.py 的围栏感知标题解析。批量 module_save_many 每项独立保存并可 verify=true，采用明确的部分成功报告，不实现跨文件事务。module_save_and_verify 在同一项目写锁下完成保存和核验，核验失败保留保存并返回最终 revision 与错误。locking.py 提供跨进程写锁，单文件写入采用临时文件替换；revision 固定于文档读取快照。

verify 将源码指纹、逐文件哈希、语义指纹、verified_at 写入本机 SQLite verification 表，不改写 Markdown。重复核验幂等；reindex 保留核验表，换机器或删除索引后需重新核验。旧文件基线兼容，本机新基线优先。module_status.changed_sources 给出 added/modified/removed 路径，旧基线没有逐文件证据时为 null，显式语义核验后补齐；不推测过期章节。source_freshness 只说明来源变化，document_verification 只记录 Agent/人工语义核对，external_checks 默认 NOT_CHECKED。

临时进度写 continuation，更新需 expected_revision，冲突返回当前 revision，省略字段保留，可只改 status=done。external_checks 保存 Agent 提供的 service/status/evidence/checked_at，仍留在有时间与任务范围的原记录中。临时任务文档可通过 continuation 引用路径并由 search 发现；done 记录不是当前指令。版本历史写 CHANGELOG 或发布记录；长期规则改变时才 patch 模块，不自动搬运临时正文。

设计哲学导航见 design-philosophy 模块，唯一原文在根目录 ZEN.md。重大设计取舍按任务需要阅读原文，不设为普通实现任务的必读依赖。

WebUI 是只读项目阅读器：自动发现项目，或直接按项目/.handoff 路径读取既有 Markdown，无需登记、overview 或初始化；正文按需读取，普通 Markdown 可直接展示。概览、模块、任务与历史分类导航，项目内 Markdown 原文可跟随链接阅读。项目路径范围内读取，不创建或修改交接文件；浏览器写 API 返回 405。CLI/MCP 保留原维护能力。移除旧 WebUI 状态缓存，打开模块时按当前文件计算来源与语义状态。

根目录和安装版启动入口统一使用 scripts/start-vervision.ps1；按语义版本选择包，通过 /api/health 检查服务身份与版本。端口被 Windows 保留或占用时绑定可用端口，用本机就绪文件传回实际 URL，重复启动复用同版本服务。HTTP 服务禁用 Windows 共享端口绑定。页面显示运行版本，最近路径和主题只存浏览器。安装包由 scripts/build-release.ps1 根据包版本生成。

## 验证与回退

- 运行 python -m unittest discover -s tests -v、真实 MCP JSON-RPC 冒烟及项目 validate。
- scripts/benchmark-mcp.py 对指定 Git 旧版本测量隔离双模块维护调用数与响应字符数，不作为 token 计费估算。
- 回退以 Git 提交为单位；Markdown 仍是长期知识事实源，本机核验记录可以丢弃后重新核对。
