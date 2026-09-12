---
schema_version: 1
type: "continuation"
id: "vervision-optimization-20260912"
title: "Vervision 可靠性与 MCP 效率优化"
module_id: "context-router"
status: "done"
next_step: "本轮已完成。后续如继续第二批，可单独评估 resolve.changed_paths 与逐文件基线；不要将 related_modules 自动视为必须更新。"
updated_at: "2026-09-12T10:11:30+08:00"
---

## 当前进度：4/4（100%，已完成）

### 已完成

1. 写入契约：部分更新保留省略字段和未知扩展字段；显式空数组清空；已有模块强制 expected_revision；新建冲突明确；无变化不重写；所有相关写操作返回 revision。
2. 核验语义：来源 FRESH/STALE/UNVERIFIED 保持兼容；新增 VERIFIED/PENDING/UNKNOWN_LEGACY/UNVERIFIED 文档核验状态；工具字段不触发自我失效。
3. MCP 效率：resolve 单请求一次受限 inventory、重叠文件 hash 复用、依赖摘要去重、默认 concise/detailed 可选、search 命中理由。
4. GUI/文档：来源状态与交接核验分开展示；说明线上配置边界；模板加入运行与发布入口；README/FORMAT 更新。
5. 验证：21 项 unittest、compileall、node --check、真实 MCP JSON-RPC、CLI resolve/verify、WebAPI 冒烟和 git diff --check 均通过。
6. Android 单次对比：inventory 7→1，digest 8→5；格式化响应 12977→5963 字符（concise）/8935（detailed）；热文件系统单次耗时约 0.04 秒，不能视为稳定 SLA。
7. context-router 交接已对照代码更新并显式核验，核验后 revision 为 670d616c07303f95。

### 有意后置

- changed_paths 与逐文件增删改基线属于第二批增强，本轮未扩展范围。
- structuredContent 未加入；需要先验证目标客户端兼容性和真实上下文收益。

### 跨 Agent 约束

如后续继续，先读取本 continuation、当前 git diff 和测试结果；保持 Markdown 为事实源、SQLite 可重建索引，不自动语义核验，不引入后台缓存或复杂状态机。
