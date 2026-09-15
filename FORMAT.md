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

工具在核验后将以下运行元数据写入本机 SQLite 的独立 verification 表，不改写 Markdown。旧文件中的这些字段仍可读取，本机新基线优先：

- `verified_at`：完成语义核对的时间。
- `verified_digest`：当时所有关联源码的内容指纹。
- `verified_document_digest`：当时交接正文和业务字段的语义核验指纹；工具维护的时间与核验字段不参与计算。
- `source_fingerprints`：仅本机核验记录保存的逐文件内容哈希，用于 `module_status.changed_sources` 的 added/modified/removed 文件级证据。没有该基线时返回 null，不猜测变化；旧基线在下一次显式语义核验时升级。

任何模块正文或字段被编辑后，都应重新进行语义核对并运行 `handoff verify <id>`。单纯刷新核验时间不能证明内容正确。旧文档只有源码基线而没有语义核验指纹时，会显示 `UNKNOWN_LEGACY`，直到下一次人工核验。

`revision` 是文档文件的内容版本，源码指纹与核验状态分别存储。重复 save/verify 不改变文件；verify 的 `changed=false` 表示 Markdown 没有变化，`verification_changed` 表示本机基线是否变化。删除索引或换机器会失去本机核验记录，需要重新核对；Markdown 知识不会丢失。普通 reindex 保留 verification 表。

continuation 支持可选 `external_checks` 数组，每项包含 `service`、`status`、`evidence`、`checked_at`，是 Agent 提供的有时间范围的观察记录，不是工具自动探测结果。更新 continuation 可直接发送变更字段，无需预读；写锁内保留省略字段，同一字段以最后一次写入为准。依赖先前读取内容时传 `expected_revision`，不匹配才报冲突；`expected_revision="new"` 表示仅创建，携带旧 revision 不会重建已删除记录。可只改 `status=done`。创建需要有效 `module_id` 和非空 `next_step`，title 默认 id、status 默认 open。Agent 判断内容属于长期知识还是临时进度，工具不按关键词猜测；版本号、APK 哈希、测试数量与发布历史应记录在 CHANGELOG 或发布记录，长期模块只保留设计和约束。

根目录或其他位置已有原文时，模块可只保留一句导航摘要、相关 aliases/tags 和 `sources: ["原文路径"]`，不复制全文。`dependencies` 表示必要模块依赖，不应被用作强制所有任务加载设计哲学的开关。阶段性任务文档用 continuation 引用路径；完成后标记 done，历史约束不自动提升为当前规则。读取模块时 continuation 仅返回 id/title/status，正文需独立读取。

读取工具默认返回 metadata、来源模式和 `sections` 标题列表。按需传入 `sections=["标题"]` 可读取唯一 ATX 标题及其子章节，或显式 `full=true` 读取该文档全文。代码围栏中的标题不参与选择；缺失或重复标题报错；父子选择重叠时不重复输出。此读取机制不要求更改 Markdown schema。

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
