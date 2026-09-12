---
schema_version: 1
type: module
id: example-module
title: "示例模块"
summary: "用一句话说明模块的职责和边界。"
aliases: ["常用名称"]
tags: ["frontend"]
sources: ["src/example/**", "config/example.json"]
dependencies: []
related_modules: []
business_rules: ["关键统计口径、合并规则或业务定义。"]
invariants: ["修改时不可破坏的数据、兼容性或安全约束。"]
consumers: ["依赖本模块行为的页面、接口、APP 或导出流程。"]
updated_at: "2026-09-10"
---

# 当前实现

写清功能流程和模块边界。可以从代码直接读取的端口、脚本列表等事实不必重复罗列。

## 设计原因与约束

- 为什么采用当前设计。
- 修改时必须保留什么。

## 已知问题与验证

- 已知坑、验证办法和回退入口。

## 运行与发布入口（可选）

- 操作脚本或文档路径：
- 必要环境变量名称（不要填写密钥值）：
- 非敏感配置所在位置：
- 核查命令：
- 最近观察日期与适用范围：

> `verified_at` 和 `verified_digest` 由 `handoff verify` 写入。外部 AI 不应伪造核验结果。
