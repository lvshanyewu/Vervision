# Vervision

![Vervision icon](assets/icon.png)

Vervision 是一个完全本地运行的 AI 项目交接与上下文路由工具。项目知识继续保存在项目自身的 `.handoff/*.md` 文件中；Vervision 负责校验格式、关联源码、检测过期、搜索内容，并通过 WebUI、CLI 和 MCP 把相关上下文交给下一个 Agent。

V1 不调用大模型，不需要在线服务，也不把 Markdown 锁进数据库。SQLite 只保存可随时重建的本地索引。

## 安装

本仓库公开的是源码、示例、模板和构建脚本；构建目录、发布压缩包、本地索引、日志及个人项目 seed 不纳入版本控制。

### Windows 安装包

解压 `Vervision-0.5.0-windows-x64.zip`，进入解压后的文件夹，在 PowerShell 中执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

也可双击 `start-vervision.cmd` 直接运行，无需安装。安装后可以从开始菜单打开 Vervision，或重新打开终端使用 `handoff` / `vervision`。

升级时先退出正在运行的 Vervision，再运行新版安装脚本。MCP 客户端需要重新连接才能加载新版工具；建议使用下面的固定安装路径，避免每次升级修改版本化 EXE 路径：

```powershell
codex mcp add vervision -- "$env:LOCALAPPDATA\Programs\Vervision\vervision.exe" mcp
```

安装程序把应用放入 `%LOCALAPPDATA%\Programs\Vervision`，不会复制或上传任何项目数据。`uninstall.ps1` 只删除程序和开始菜单快捷方式，保留所有项目中的 `.handoff` 以及本地索引数据。

在源码目录双击 `启动 Vervision.cmd`，或在解压后的安装包中双击 `start-vervision.cmd`。脚本会启动服务并打开实际可用的地址；8765 被占用或被 Windows 保留时自动选择其他可用端口，不需要管理员权限或更改系统端口设置。重复双击会复用同版本服务，顶部显示实际运行版本。请使用脚本打开的地址，而不是固定访问 8765。

启动状态保存在 `%LOCALAPPDATA%\Vervision\logs\webui-8765.json`，包含实际 URL；日志为同目录的 `webui.log` 和 `webui-error.log`。脚本核对专用健康接口和版本，启动失败时直接显示退出码与错误摘要。

### 在浏览器中阅读项目

1. 从左侧“我的项目”选择自动发现的项目，或在“打开其他项目”中输入项目文件夹路径后点击“打开”。也可输入 `.handoff` 文件夹本身的路径。
2. 选择概览、模块知识、进行中的任务或历史记录；搜索框可搜索文件标题、路径和正文。
3. 点击文档中的项目内 Markdown 链接可阅读原文；模块的“来源与核验详情”默认折叠。

已有交接文件无需先执行 init 或登记项目。即使没有 overview 或规范 frontmatter，也可以阅读 `.handoff` 内现有的 Markdown。没有交接目录时页面会明确提示，选择另一个项目即可。最近打开的路径只记在当前浏览器中。

WebUI 是只读阅读器，不提供新建、编辑、删除、归档、导入或核验写入；浏览器 API 同样拒绝写操作。深浅主题使用暖色中性背景、黑白主按钮及低饱和状态标签。CLI/MCP 仍提供 Agent 所需的维护能力。

### 从源码安装

需要 Python 3.10 或更高版本：

```powershell
cd D:\vervision
python -m pip install -e .
handoff --help
```

运行时没有第三方 Python 依赖。

## 第一次体验

仓库包含一个最小 Demo：

```powershell
handoff init D:\vervision\examples\demo-project
handoff verify greeting --project D:\vervision\examples\demo-project
handoff status --project D:\vervision\examples\demo-project
handoff gui
```

修改 Demo 的 `app/main.py` 后重新执行 `handoff status`，`greeting` 会从 `FRESH` 变为 `STALE`。

## 接入一个项目

```powershell
cd D:\your-project
handoff init . --id your-project --title "Your Project"
```

这会创建：

```text
.handoff/
├── overview.md
├── modules/
├── continuations/
└── archive/
```

将整理好的模块文件放入 `.handoff/modules/`，然后运行：

```powershell
handoff validate
handoff reindex
handoff gui
```

以上初始化步骤用于创建新交接，而不是浏览已有项目的前置条件。GUI 只读取文件；创建、修改和核验仍由 Agent 通过 CLI/MCP 或直接维护 Markdown 完成。

完整格式与外部文字 AI 的导入规则见 [FORMAT.md](FORMAT.md)，可以直接把 `templates/` 中的三份模板交给其他 Agent。

## 导入已经整理好的旧 Hand-off

Vervision 不使用 AI 理解旧文档。先让外部文字 Agent 按模板完成拆分，再执行：

```powershell
handoff import D:\prepared-handoff --project D:\your-project
```

系统会先检查字段、重复 ID、模块引用和源码路径。批次有错误时不会导入。默认不覆盖现有文件；确认要替换时使用 `--replace`。

## Freshness 工作方式

模块的 `sources` 可以登记文件、目录或 glob。Agent 对照真实代码确认模块正文正确后运行：

```powershell
handoff verify essay-quickref --project D:\myseoul
```

Vervision 将源码内容指纹、交接语义指纹和核验时间保存在本机索引，不再写回模块文件。源码与正文相同时重复核验是无变化操作，正文 revision 保持不变。以后只要关联源码内容变化，来源状态就成为 `STALE`；来源路径消失也会成为 `STALE`。交接正文或业务字段被修改后，独立的文档核验状态显示 `PENDING`。旧文件基线仍可读取，本机新记录优先。换机器或删除索引后需重新核验；reindex 保留核验记录。

Freshness 只回答“关联代码在核验后是否变化”。它不能代替语义核对，也不表示生产环境仍然在线。

## MCP 接入 Codex

### Codex 插件

插件源码在 [plugins/vervision](plugins/vervision/README.md)，包含一个简短 Skill 和现有 stdio MCP 配置，采用官方仍支持的 plugin-creator 兼容格式。先安装本地 Vervision，再通过 Codex plugin-creator 加入个人 marketplace 并安装。插件不复制核心逻辑，Core 不依赖 Codex，原 CLI/MCP/WebUI 继续可用。Python 或 EXE 必须在运行插件的本机可用；安装到云端不会自动访问本地 Windows 文件。

0.5.0 已实现当前小节检索与按需变化检查，具体行为和边界见[检索与 STALE 说明](docs/retrieval-and-stale-plan.md)。插件 Skill 与 Core 应一起升级；旧 EXE 不会因为更新 Skill 自动获得新接口。

### 直接配置 MCP

安装 Windows 包后执行：

```powershell
codex mcp add vervision -- "$env:LOCALAPPDATA\Programs\Vervision\vervision.exe" mcp
```

从源码运行则可以使用明确的解释器和项目路径：

```powershell
codex mcp add vervision -- python -m vervision mcp
```

第二种方式要求 Codex 启动 MCP 时的 Python 能找到已安装的 `vervision` 包。命令格式已按当前 Codex CLI 的 `mcp add` 帮助核对；也可以通过 `codex mcp list` 确认配置。

MCP 默认返回 `structuredContent`，文本区只有短提示，不重复嵌套大段 JSON。读取默认返回 metadata 和 ATX 章节标题；`sections=["当前实现"]` 按标题读取正文（包含子章节），`full=true` 获取单份文档全文和诊断，二者不能同时使用。客户端须支持结构化工具结果。接口如下：

- `resolve`：返回会话 `scope_id`、架构摘要、相关模块 revision、约束与下一步批量读取参数。显式项目优先，其次工作区包含关系；无法明确定位且有多个候选时拒绝自动选择，关键词和文档 ID 不再触发跨项目选择。`detail=detailed` 返回检索诊断。scope 绑定当前 MCP 服务会话，重启后重新 resolve；scope 与显式 project/workspace 冲突会拒绝调用。
- `search`：默认搜索当前知识和未完成任务，最多五项；`has_more` 表示还有结果，可缩小查询或设置 `limit`（1..50）。`include_history=true` 展开 done 任务与历史正文。附带类型读取参数，命中唯一末级小节时 next_action 直接携带 sections，否则先读摘要与标题。标题、别名、标签、来源和依赖高于正文，正文得分封顶；默认过滤常见版本流水行和明确的历史标题小节，摘要与排序使用同一份过滤文本。英文关键词按词边界匹配，避免 ui 命中 build。精确登记的文件路径/文件名优先于泛关键词；resolve 存在精确模块命中时只返回这些模块，仍最多三个。resolve 区分 `modify`（建议修改）、`read`（建议读取）、依赖摘要的 `related`（仅关联）；建议不代表必须更新。
- `module_get`、`overview_get`、`continuation_get`：明确类型的读取接口；`handoff_get` 保留兼容。
- `module_get_many`：一次读取 `ids`，最多 50 个，失败项单独报告，项目选择信息不逐项重复。`sections` 对每份模块使用相同的标题选择；不同标题宜分别读取。标题必须唯一，重复或不存在时明确报错。不会静默截断正文；很大的章节仍可选择更细的子标题或直接查看原文件。
- `module_status`：单独检查 Freshness 和 `change_summary` 增删改计数；`review=true` 按需返回当前模块中引用变更文件的候选位置，最多五项并报告遗漏数，明确未作语义判断。
- `module_save`：新增或部分更新模块；更新已有模块必须使用 `expected_revision`，省略字段保留、显式空数组清空。无变化保存不会重写文件。
- `module_patch`：携带 `id`、`expected_revision`，用 `fields` 部分更新元数据，用 `sections: [{heading, body}]` 替换 Markdown 标题下内容。标题保留，替换范围包含其子标题；同名标题、缺失标题报错，代码围栏内的标题忽略。不支持 Setext 标题和任意 JSON Patch，避免多套修改语法。
- `module_save_many`：`changes` 中每项使用 save 字段或 patch 的 fields/sections，可设置 `verify=true`。采用明确的部分成功模式，不做批次回滚；每项返回最终 revision、changed、verified 或错误。重复 ID 在写入前拒绝。每项持有项目写锁并以文件替换方式落盘，防止多个 Vervision Agent 同时覆盖。
- `module_save_and_verify`：一次保存/patch 并声明 Agent 已完成语义核对。源码路径失效时返回 `verified=false` 和 `verification_error`，已保存内容及最终 revision 保留。只需记录知识时用普通 save，不必每轮核验。
- `module_verify`：Agent 完成语义核对后刷新本机基线。`changed=false` 表示文件不变，`verification_changed` 表示基线是否变化。不会检查正文数字、APK 哈希或外部服务。
- `continuation_save`：记录进度、阻塞、下一步及可选 external_checks（service/status/evidence/checked_at）。普通部分更新无需预读或 revision；在写锁内合并，省略字段保留，可只改 status=done。依赖读到的版本时传 expected_revision，只有不匹配才报冲突；expected_revision="new" 表示仅创建。无 revision 时同一字段后写覆盖先写，正文改写宜携带 revision。发布进度不必修改模块正文。

所有接口均接受 `scope_id`，无需重复 project/workspace。冲突返回当前 revision、请求与当前字段差异，以及最多 4000 字符的正文差异；不会自动覆盖冲突，也不会假称掌握旧版本全文。

典型开发流程为 `resolve → 按需执行 next_actions（相关小节，或摘要与标题）→ 查看源码 → 修改`。不同匹配小节分组返回批量读取参数。resolve/search 不再建议默认加载全文；已有足够证据时可以跳过读取，直接使用 revision 做字段或段落 patch。默认模块读取仅列未完成 continuation 的 id/title/status；full=true 才列全部任务索引，历史正文须显式 continuation_get，避免旧指令混入当前上下文。单纯补传 APK 的任务通常只更新 continuation，长期规则真正改变时才更新模块。

`module_status.changed_sources` 列出核验以来 added/modified/removed 的相对文件路径，不提供核验基线代码 diff 或语义判断。`change_summary` 给出增删改计数；`review=true` 的候选仅依据当前模块正文中的直接路径/文件名引用，可能无关或遗漏，不能据此断言某小节过期。没有逐文件基线时返回 null（未知），已建立基线且无变化时为 []；下一次完成语义核对后的 verify 会补齐旧基线。它反映登记来源集合的变化，包括 sources 配置调整，不等同于 Git 工作区状态。外部验证仍通过 continuation 的 external_checks 显式读取，不将过去某环境的结果当作模块当前状态。

本项目的设计哲学唯一原文是根目录 [ZEN.md](ZEN.md)。`.handoff/modules/design-philosophy.md` 仅用现有 aliases/tags/sources 为重大设计决策导航，不复制原文，也不成为所有模块的依赖。其他外部文档也可用现有来源路径登记；临时任务说明可在 continuation 的标题、next_step 和正文中引用原路径，再用 search 定位，不需要新建 task_note 类型。已完成 continuation 是历史记录，不是当前用户指令。

```json
{"scope_id":"<resolve 返回值>","changes":[{"id":"release-engineering","expected_revision":"<revision>","sections":[{"heading":"发布渠道","body":"稳定的上传规则。"}],"verify":true}]}
```

本轮不引入发布数据库、批次事务引擎或自动语义判断。长期规则的提升用显式 module_patch，再把 continuation 标记 done；不自动搬运临时正文，以免把发布流水带回模块。

建议在项目 Agent 规则中加入：

```text
需要项目交接知识时，使用 Vervision resolve 查询当前任务；通常使用默认 concise 响应，已有充分证据可跳过。
使用返回的 scope_id 和 module_get_many 参数按需读取正文；来源为 STALE/UNVERIFIED，或文档核验为 PENDING/UNKNOWN_LEGACY 时，先核对真实代码与当前运行环境。
更新已有模块时携带刚读取的 expected_revision；省略字段表示保留，显式空数组才表示清空。
临时进度更新 continuation；稳定知识优先 patch，并把多模块修改合并到 module_save_many。只有完成语义核对才设置 verify=true；核验不会改变正文 revision。FRESH 不代表测试数量、APK 哈希或外部服务已验证。
```

支持 MCP Roots 的客户端会把当前工作区直接交给 Vervision。其他客户端可在工具参数中传 `workspace`；两者都没有时，Vervision 使用进程目录、父目录、相邻目录与本机项目登记表推断。

## CLI

```text
handoff init [path]
handoff validate [--project path-or-id]
handoff import <prepared-path> [--project path-or-id] [--replace]
handoff search <query> [--project path-or-id] [--limit 1..50] [--include-history]
handoff resolve <task> [--project path-or-id] [--detail concise|detailed]
handoff status [--project path-or-id]
handoff verify <module-id> [--project path-or-id]
handoff reindex [--project path-or-id]
handoff gui [--port 8765]
handoff mcp
```

项目注册表和可重建索引位于 `%LOCALAPPDATA%\Vervision`。主数据始终位于各项目的 `.handoff` 文件夹，适合随项目 Git 保存。

## 当前边界

V1 搜索采用字段加权的本地文本匹配，不包含向量检索。WebUI 的 Markdown 预览只支持常用标题、列表、代码和引用。跨机器协作依赖你原有的 Git/文件同步方式；Vervision 不实现云同步、账户、权限或并发任务认领。

## 开发与打包

```powershell
python -m unittest discover -s tests -v
python -m vervision gui --no-browser
```

重新构建 Windows 发布包：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-release.ps1
```

Windows 单文件程序使用 PyInstaller 构建，随后将程序、模板和安装脚本组成可转移的 ZIP 安装包。构建脚本位于 `scripts/build-release.ps1`。
