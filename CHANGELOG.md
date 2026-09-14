# Changelog

## 0.4.1

- 修复 Windows 保留或占用 8765 时 WebUI 无法启动：自动绑定可用端口，启动器读取实际 URL 并校验服务身份和版本，重复启动复用同版本服务。
- Windows HTTP 服务禁用共享端口绑定；启动失败显示退出码和日志摘要，打包程序按语义版本选择，开始菜单统一走就绪启动器。
- WebUI 改为只读项目阅读器：可直接输入任意项目或 .handoff 目录路径，无需登记或初始化；支持缺少 overview 的普通 Markdown。
- 浏览概览、模块、进行中任务与历史记录，全文搜索、项目内原文链接、最近项目与可见版本；去除全部浏览器写操作及旧状态缓存。
- 按中性暖白／暖黑配色更新页面，使用纯色背景层级、黑白反色主按钮、低饱和状态标签与响应式布局。

兼容变化：旧 WebUI 写入和模块管理 API 已移除；WebUI 新只读 API 为 /api/health、/api/projects、/api/documents、/api/document。CLI/MCP 写入接口不受影响。

## 0.4.0

- 将根目录 ZEN.md 登记为设计哲学唯一原文；现有模块 metadata 只负责相关任务导航，不增加全局必读依赖或新文档类型。
- 英文检索使用词边界，避免 ui/build 等子串误召回；精确登记的文件路径或文件名优先于泛关键词。
- resolve/search 下一步默认读取摘要和章节标题；支持按唯一 ATX 标题读取，复用 patch 解析，不静默截断或重复父子内容。
- 模块读取只附带 continuation 索引，全文不再携带历史交接正文；continuation_save 工具说明明确 revision 契约。
- 删除根据“下一步”或 PENDING 等关键词猜测临时进度的保存警告，避免长期接口说明被误报。
- 本机核验基线增加逐文件哈希，module_status 返回 added/modified/removed 来源证据；无逐文件基线时明确返回未知。

兼容变化：模块 full=true 不再内嵌 continuation 正文；需显式 continuation_get。检索返回的 next_action 默认 full=false。工具数量与 Markdown schema 不变，未增加意图分类器、外部状态聚合、Git 包装或指令生命周期状态机。

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
