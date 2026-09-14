---
schema_version: 1
type: "continuation"
id: "zen-routing-040"
title: "Zen 路由与渐进读取优化 0.4.0"
module_id: "context-router"
status: "done"
next_step: "本轮源码、知识登记、验证及 0.4.0 安装包已完成。"
updated_at: "2026-09-14T09:21:22+08:00"
external_checks: [{"service": "local unittest", "status": "passed", "evidence": "49 tests passed", "checked_at": "2026-09-14T09:21:22+08:00"}, {"service": "Windows 0.4.0 package and MCP", "status": "passed", "evidence": "EXE JSON-RPC and ZIP integrity passed", "checked_at": "2026-09-14T09:21:22+08:00"}]
---

## 反馈来源与核对

本轮最新真实反馈是用户随任务提供的九项 Agent 使用反馈；同时按需读取 mcp-efficiency-030 与 vervision-optimization-20260912 两份已完成记录，对照 cab6f61 / 当前 0.3.0 源码。未接入反馈中的 Android 项目，未声称完整复现其外部服务状态。实际通过 CLI resolve 和 MCP call_tool、独立 stdio/EXE 调用使用本项目知识，并用隔离测试验证具体行为。

## 逐项取舍

1. 召回：0.3.0 已有最多三个结果、正文降权与流水过滤；仍存在 ui 命中 build/guidelines 的词片段问题。改为英文词边界、精确登记路径/文件名优先，保留原评分，不增加任务意图分类器。
2. 读取：resolve 原先建议 full=true，且模块全文带出所有 continuation 正文。改为摘要/标题导航、按唯一 ATX 章节读取、历史交接只带索引。读取与 patch 共用解析。未增加 include 字段语言、token 估算器、输出截断与分页状态；大章节可选子标题或直接查看原文件。
3. freshness：新增本机逐文件哈希，返回 added/modified/removed；旧基线返回 null，显式核验后升级。不猜测 likely_stale_sections。
4. continuation：当前实现已强制 expected_revision 并在 conflict 返回当前 revision，只补齐工具描述，保留乐观锁，不自动合并覆盖。
5. external_checks：不聚合成模块当前状态。现有记录未规范环境、有效期与服务身份，按最新时间覆盖会制造确定性；通过原 continuation 保留 service/status/evidence/checked_at。
6. 阶段文档：现有 continuation 可引用原路径并用 search 发现；没有足够收益增加 task_note 类型。Zen 使用现有模块 aliases/tags/sources 导航到根目录唯一原文，不复制、不设全局依赖。
7. 历史约束：保留已有 done/archive 边界，去掉模块读取隐式注入历史正文；显式查历史时由 Agent 结合当前请求判断，不增加 instruction_status/superseded_by 状态机。
8. Git 状态：Agent 可以直接使用 git status/diff/log，未添加仓库状态包装。
9. 重复知识：模块只更新长期契约、README/FORMAT 说明接口，版本行为写 CHANGELOG，验证与过程留在本 continuation。

实际更新长期模块时还发现关键词警告把接口中的“下一步”与 PENDING 当作临时进度。删除该猜测规则，归档位置由 Agent 判断。

## 验证与产物

49 项 unittest 通过（包含新增路由、Zen 原文导航、章节边界、历史正文隔离、逐文件基线与冲突契约回归）；compileall、项目 validate、git diff --check 通过。
源码 Python 与 dist/vervision-0.4.0.exe 均通过独立 MCP JSON-RPC：版本、14 个工具、Zen 精确 resolve、默认非全文、选择子章节、全文不内嵌 continuation、原文路径可发现。Windows ZIP 完整性与 README/ZEN/CHANGELOG 包内文件检查通过。
产物：dist/Vervision-0.4.0-windows-x64.zip 与 dist/vervision-0.4.0.exe。源码与包版本均为 0.4.0；本轮未替换已安装运行进程，现有客户端需要自行重启连接新版本才能使用新接口。

## 响应量样例

在写入本记录前，使用相同当前项目文档、隔离 LOCALAPPDATA，对比 Git cab6f61 的 core/formats/mcp_server/locking/__init__ 与当前源码。任务“项目发现”：旧版 resolve 后执行返回的 next_action，两次调用 7551 字符；新版 resolve、next_action，再 module_get(sections=["当前实现"])，三次调用 4418 字符，减少 41.5%。按 json.dumps(ensure_ascii=False,separators=(",",":")) 累加工具结果，未包含工具 schema、请求与协议封装，不是实际计费 token 或普遍性能承诺。额外一次便宜调用替代历史正文加载。
