# Vervision

![Vervision icon](icon.png)

Vervision 是一个完全本地运行的 AI 项目交接与上下文路由工具。项目知识继续保存在项目自身的 `.handoff/*.md` 文件中；Vervision 负责校验格式、关联源码、检测过期、搜索内容，并通过 WebUI、CLI 和 MCP 把相关上下文交给下一个 Agent。

V1 不调用大模型，不需要在线服务，也不把 Markdown 锁进数据库。SQLite 只保存可随时重建的本地索引。

## 安装

本仓库公开的是源码、示例、模板和构建脚本；构建目录、发布压缩包、本地索引、日志及个人项目 seed 不纳入版本控制。项目图标位于 `icon.png`，也会随 Windows 发布 ZIP 一起打包。

### Windows 安装包

解压 `Vervision-0.2.1-windows-x64.zip`，右键 `install.ps1` 选择“使用 PowerShell 运行”。安装后可以从开始菜单打开 Vervision，或重新打开终端使用 `handoff` / `vervision`。

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

Vervision 将源码内容指纹、交接语义指纹和核验时间写回模块文件。以后只要关联源码内容变化，来源状态就成为 `STALE`；来源路径消失也会成为 `STALE`。交接正文或业务字段被修改后，独立的文档核验状态显示 `PENDING`。旧文档没有语义指纹时显示 `UNKNOWN_LEGACY`，可继续读取并在下次人工核验时升级。

Freshness 只回答“关联代码在核验后是否变化”。它不能代替语义核对，也不表示生产环境仍然在线。

## MCP 接入 Codex

安装 Windows 包后执行：

```powershell
codex mcp add vervision -- vervision mcp
```

从源码运行则可以使用明确的解释器和项目路径：

```powershell
codex mcp add vervision -- python -m vervision mcp
```

第二种方式要求 Codex 启动 MCP 时的 Python 能找到已安装的 `vervision` 包。命令格式已按当前 Codex CLI 的 `mcp add` 帮助核对；也可以通过 `codex mcp list` 确认配置。

Vervision MCP 提供七个工具：

- `resolve`：推荐的第一入口。结合客户端工作区、父目录、相邻目录、已登记项目和任务相关度选择项目；不确定时返回候选项目和下一次调用参数。默认 `detail=concise` 返回架构摘要、相关模块、必要约束、来源状态和一份下一步调用；需要完整来源和诊断元数据时使用 `detail=detailed`。
- `search`：搜索全部文档类型，每条结果附带下一步 `handoff_get` 参数。
- `handoff_get`：统一读取 overview、module 和 continuation；旧版 `module_get` 调用仍兼容。
- `module_status`：单独检查 Freshness。
- `module_save`：新增或部分更新模块；更新已有模块必须使用 `expected_revision`，省略字段保留、显式空数组清空。无变化保存不会重写文件。
- `module_verify`：Agent 完成语义核对后刷新源码与文档核验基线，并返回写入后的 revision。
- `continuation_save`：记录跨会话的进度、阻塞和下一步。

建议在项目 Agent 规则中加入：

```text
开始功能开发前，先调用 Vervision resolve 查询当前任务；通常使用默认 concise 响应。
使用返回的 handoff_get 参数按需读取正文；来源为 STALE/UNVERIFIED，或文档核验为 PENDING/UNKNOWN_LEGACY 时，先核对真实代码与当前运行环境。
更新已有模块时携带刚读取的 expected_revision；省略字段表示保留，显式空数组才表示清空。
完成修改后，更新受影响模块或任务接续；只有对照代码完成语义核对后才调用 module_verify，并继续使用它返回的新 revision。
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
