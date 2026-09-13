# Vervision

![Vervision icon](assets/icon.png)

Vervision 是一个完全本地运行的 AI 项目交接与上下文路由工具。项目知识继续保存在项目自身的 `.handoff/*.md` 文件中；Vervision 负责校验格式、关联源码、检测过期、搜索内容，并通过 WebUI、CLI 和 MCP 把相关上下文交给下一个 Agent。

V1 不调用大模型，不需要在线服务，也不把 Markdown 锁进数据库。SQLite 只保存可随时重建的本地索引。

## 安装

本仓库公开的是源码、示例、模板和构建脚本；构建目录、发布压缩包、本地索引、日志及个人项目 seed 不纳入版本控制。

### Windows 安装包

解压 `Vervision-0.3.0-windows-x64.zip`，进入解压后的文件夹，在 PowerShell 中执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

也可双击 `start-vervision.cmd` 直接运行，无需安装。安装后可以从开始菜单打开 Vervision，或重新打开终端使用 `handoff` / `vervision`。

升级时先退出正在运行的 Vervision，再运行新版安装脚本。MCP 客户端需要重新连接才能加载新版工具；建议使用下面的固定安装路径，避免每次升级修改版本化 EXE 路径：

```powershell
codex mcp add vervision -- "$env:LOCALAPPDATA\Programs\Vervision\vervision.exe" mcp
```

安装程序把应用放入 `%LOCALAPPDATA%\Programs\Vervision`，不会复制或上传任何项目数据。`uninstall.ps1` 只删除程序和开始菜单快捷方式，保留所有项目中的 `.handoff` 以及本地索引数据。

浏览器中的 `http://127.0.0.1:8765/` 只有在 Vervision 进程运行时才能访问。在源码目录双击 `启动 Vervision.cmd`，或在解压后的安装包中双击 `start-vervision.cmd`；脚本会自动寻找程序、启动本地服务，并在服务就绪后打开浏览器。重复双击时会直接打开已经运行的页面。

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

GUI 默认在 `http://127.0.0.1:8765` 打开。它可以查看、搜索、新建、编辑、核验和归档模块。归档不会直接删除文件，而是移动到 `.handoff/archive/`。

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

安装 Windows 包后执行：

```powershell
codex mcp add vervision -- "$env:LOCALAPPDATA\Programs\Vervision\vervision.exe" mcp
```

从源码运行则可以使用明确的解释器和项目路径：

```powershell
codex mcp add vervision -- python -m vervision mcp
```

第二种方式要求 Codex 启动 MCP 时的 Python 能找到已安装的 `vervision` 包。命令格式已按当前 Codex CLI 的 `mcp add` 帮助核对；也可以通过 `codex mcp list` 确认配置。

MCP 默认返回 `structuredContent`，文本区只有短提示，不重复嵌套大段 JSON。读取默认不含正文，使用 `full=true` 获取全文和诊断；客户端须支持结构化工具结果。接口如下：

- `resolve`：返回会话 `scope_id`、架构摘要、相关模块 revision、约束与下一步批量读取参数。显式项目优先，其次工作区包含关系；无法明确定位且有多个候选时拒绝自动选择，关键词和文档 ID 不再触发跨项目选择。`detail=detailed` 返回检索诊断。scope 绑定当前 MCP 服务会话，重启后重新 resolve；scope 与显式 project/workspace 冲突会拒绝调用。
- `search`：搜索全部文档类型，附带正式的 `module_get`、`overview_get` 或 `continuation_get` 参数。标题、别名、标签、来源和依赖高于正文，正文得分封顶并过滤常见版本流水行。resolve 区分 `modify`（建议修改）、`read`（建议读取）、依赖摘要的 `related`（仅关联）；建议不代表必须更新。
- `module_get`、`overview_get`、`continuation_get`：明确类型的读取接口；`handoff_get` 保留兼容。
- `module_get_many`：一次读取 `ids`，最多 50 个，失败项单独报告，项目选择信息不逐项重复。
- `module_status`：单独检查 Freshness。
- `module_save`：新增或部分更新模块；更新已有模块必须使用 `expected_revision`，省略字段保留、显式空数组清空。无变化保存不会重写文件。
- `module_patch`：携带 `id`、`expected_revision`，用 `fields` 部分更新元数据，用 `sections: [{heading, body}]` 替换 Markdown 标题下内容。标题保留，替换范围包含其子标题；同名标题、缺失标题报错，代码围栏内的标题忽略。不支持 Setext 标题和任意 JSON Patch，避免多套修改语法。
- `module_save_many`：`changes` 中每项使用 save 字段或 patch 的 fields/sections，可设置 `verify=true`。采用明确的部分成功模式，不做批次回滚；每项返回最终 revision、changed、verified 或错误。重复 ID 在写入前拒绝。每项持有项目写锁并以文件替换方式落盘，防止多个 Vervision Agent 同时覆盖。
- `module_save_and_verify`：一次保存/patch 并声明 Agent 已完成语义核对。源码路径失效时返回 `verified=false` 和 `verification_error`，已保存内容及最终 revision 保留。只需记录知识时用普通 save，不必每轮核验。
- `module_verify`：Agent 完成语义核对后刷新本机基线。`changed=false` 表示文件不变，`verification_changed` 表示基线是否变化。不会检查正文数字、APK 哈希或外部服务。
- `continuation_save`：记录进度、阻塞、下一步及可选 external_checks（service/status/evidence/checked_at）。更新须带 expected_revision，省略字段保留，可只改 status=done。发布进度不必修改模块正文。

所有接口均接受 `scope_id`，无需重复 project/workspace。冲突返回当前 revision、请求与当前字段差异，以及最多 4000 字符的正文差异；不会自动覆盖冲突，也不会假称掌握旧版本全文。

典型开发流程缩短为 `resolve → module_get_many(full=true) → module_save_many`，多个模块的核验可合并到最后一次调用。已有充分上下文时可直接使用 resolve 返回的 revision 进行字段或段落 patch。单纯补传 APK 的任务通常只更新 continuation，长期规则真正改变时才更新模块。

```json
{"scope_id":"<resolve 返回值>","changes":[{"id":"release-engineering","expected_revision":"<revision>","sections":[{"heading":"发布渠道","body":"稳定的上传规则。"}],"verify":true}]}
```

本轮不引入发布数据库、批次事务引擎或自动语义判断。长期规则的提升用显式 module_patch，再把 continuation 标记 done；不自动搬运临时正文，以免把发布流水带回模块。

建议在项目 Agent 规则中加入：

```text
开始功能开发前，先调用 Vervision resolve 查询当前任务；通常使用默认 concise 响应。
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
handoff search <query> [--project path-or-id]
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
