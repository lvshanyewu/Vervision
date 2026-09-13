---
schema_version: 1
type: "continuation"
id: "mcp-efficiency-030"
title: "MCP 调用成本与交接安全优化 0.3.0"
module_id: "context-router"
status: "done"
next_step: "新版已安装且 MCP 配置已指向固定安装路径；当前 Codex 任务仍持有旧连接，需要客户端重载 MCP 或重启后再验证。"
updated_at: "2026-09-12T20:05:36+08:00"
---

完成 scope、安全项目定位、字段/标题 patch、批量操作、独立本机核验、structuredContent、continuation 局部更新与外部证据。未增加 JSON Patch、跨文件事务或自动规则提升；采用显式 patch 和逐项部分成功。

验证：39 项 unittest 通过；compileall、node --check、项目 validate 和 git diff --check 通过。实际 0.3.0 EXE 的 JSON-RPC 冒烟覆盖 14 个工具列表、scope、合并保存核验和幂等性；WebAPI 冒烟确认核验后立即刷新状态且 revision 不变。

隔离双模块样例：维护调用 7→3；响应 9892→7051 字符，减少 28.7%。不是实际模型 token 计费，不包含工具 schema 和请求体。复测脚本 scripts/benchmark-mcp.py。

Windows EXE/ZIP 已生成并验证。当前会话的旧 MCP 进程不会热加载新接口；新版现已安装到固定 Programs/Vervision 路径，WebUI 已重启到 0.3.0，独立 MCP 连接已验证 14 个工具与 scope；当前 Codex 任务连接仍是旧进程，未执行 Git commit/push。

图标移至 assets/icon.png；README 安装步骤、安装脚本及 ZIP 打包路径已同步。
