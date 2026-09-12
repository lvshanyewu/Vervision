# Vervision Hand-off 格式规范 v1

项目知识保存在项目根目录的 `.handoff/` 中：

```text
.handoff/
├── overview.md
├── modules/
│   └── <module-id>.md
├── continuations/
│   └── <task-id>.md
└── archive/
```

每个文件由 YAML 风格 frontmatter 和 Markdown 正文组成。为了让格式易于手写、易于 AI 生成且不依赖第三方 YAML 库，V1 frontmatter 遵循一个明确子集：每行一个 `key: value`；数组和对象使用 JSON 语法；不支持缩进列表、多行 YAML 值或锚点。

## 字段

`overview` 必填：`schema_version`、`type`、`id`、`title`、`summary`。建议增加 `architecture_summary`，用一两句话描述入口、核心组件和数据落点；`resolve` 会直接返回它。

`module` 必填：`schema_version`、`type`、`id`、`title`、`summary`、`sources`。推荐加入 `aliases`、`tags`、`dependencies`、`related_modules`、`business_rules`、`invariants`、`consumers`。后三项分别记录关键业务口径、不可破坏约束和跨模块消费者，保持短小，不需要因此继续拆分模块。

`continuation` 必填：`schema_version`、`type`、`id`、`title`、`module_id`、`status`、`next_step`。`status` 使用 `open`、`blocked` 或 `done`。

`id` 只能包含小写字母、数字、点、下划线和连字符。`sources` 是相对于项目根目录的文件、目录或 glob。模块关系引用其他模块的 `id`。

工具在核验后写入：

- `verified_at`：完成语义核对的时间。
- `verified_digest`：当时所有关联源码的内容指纹。
- `verified_document_digest`：当时交接正文和业务字段的语义核验指纹；工具维护的时间与核验字段不参与计算。

任何模块正文或字段被编辑后，都应重新进行语义核对并运行 `handoff verify <id>`。单纯刷新核验时间不能证明内容正确。旧文档只有源码基线而没有语义核验指纹时，会显示 `UNKNOWN_LEGACY`，直到下一次人工核验。

## 状态语义

- `FRESH`：关联源码与最近一次核验基线一致。
- `STALE`：关联源码已变化，或登记的来源路径已经失效。
- `UNVERIFIED`：还没有建立过核验基线。

状态只说明代码自上次核验后是否变化。它不证明线上服务仍在运行，也不自动证明文档语义正确。

`document_verification` 独立表示当前交接内容是否仍与最近一次人工语义核验一致：`VERIFIED` 表示一致，`PENDING` 表示交接内容后来被修改，`UNKNOWN_LEGACY` 表示旧文档没有语义指纹。它不会自动核验正文。

## 外部文字 AI 的导入约定

外部 AI 应只生成符合本规范的文件，不应填写 `verified_digest`。将文件放入一个临时目录后执行：

```powershell
handoff import D:\prepared-handoff --project D:\target-project
```

导入会检查字段、重复 ID、模块引用和 source 路径。存在错误时整个批次不会写入。目标已存在时默认拒绝覆盖；明确需要覆盖才加入 `--replace`。
