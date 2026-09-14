---
schema_version: 1
type: "module"
id: "design-philosophy"
title: "Zen of Vervision — 设计哲学原文导航"
summary: "根目录 ZEN.md 是设计哲学的唯一 canonical source；重大设计决策应阅读原文，小型实现或机械修改无需默认加载全文。"
aliases: ["ZEN.md", "Zen of Vervision", "设计哲学", "架构决策", "上下文路由", "上下文检索", "元数据设计", "Agent 自主性", "产品边界", "token 效率"]
tags: ["architecture", "context routing", "retrieval", "MCP", "metadata", "agent autonomy", "token efficiency", "product boundaries"]
sources: ["ZEN.md"]
dependencies: []
related_modules: ["context-router"]
---

# 何时阅读原文

涉及架构、context routing、retrieval、MCP 契约、metadata、agent autonomy、token efficiency 或产品边界的重大设计取舍时，直接阅读项目根目录 [ZEN.md](../../ZEN.md)。本模块只负责发现与导航，不复制或改写原文原则。

小型实现、格式调整、机械替换可由 Agent 判断是否需要原文；本模块不是其他模块的必读依赖。项目入口约定见 [AGENTS.md](../../AGENTS.md)。
