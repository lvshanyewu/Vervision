# Changelog

## 0.3.0

- MCP resolve 返回会话 scope 和模块 revision；项目不明确时不再按关键词或唯一模块 ID 跨项目选择。
- 增加正式类型读取、批量读取、标题/字段 patch、批量保存与合并核验；批量逐项报告成功、冲突及核验失败。
- 核验运行元数据保存到本机索引，重复核验幂等，不改变 Markdown、正文 revision 或 Git 工作区。
- MCP 默认返回精简 structuredContent；full=true 才返回正文和完整诊断。
- 降低历史版本流水对检索的影响；continuation 支持局部更新、done 和外部检查证据。
- 文档读版本固定到读取快照；项目写锁及文件替换避免 Vervision 并发写入覆盖和半文件读取。

兼容变化：读取接口默认不再返回正文；更新 continuation 需 expected_revision；多项目模糊选择现在要求显式定位。旧 Markdown 核验字段仍兼容。新核验基线不随 Git 传播，换机器需重新核验。

本轮采用字段/标题 patch 与部分成功批量，不引入 JSON Patch、跨文件事务引擎、自动语义判断或新的发布记录系统。长期规则提升通过显式 module_patch，再完成 continuation。

隔离双模块维护样例（基于升级前 HEAD）：MCP 调用从 7 次降为 3 次，序列化响应从 9892 字符降为 7051 字符（约 28.7%）。这是包含全文读取的响应体积测量，不是实际模型 token 计费；不包含工具 schema 与请求体。可用 `python scripts/benchmark-mcp.py <旧版本提交>` 复测。
