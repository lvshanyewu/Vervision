# 检索与 STALE 使用说明（0.5.0）

实现遵循 ZEN.md：用已有标题、路径和哈希缩小阅读范围，不增加必填元数据、源码快照或语义服务。

## 检索当前知识

search 默认返回最多五项，包含模块、概览和未完成 continuation。has_more=true 时可缩小查询或增加 limit（1..50）。CLI 对应 --limit 和 --include-history。

默认跳过 done 任务、明确标为 History/Changelog/Release notes/历史/发布记录/版本历史等的标题及其子节，并沿用版本流水行过滤。排序、命中字段和 snippet 使用同一份文本。它不会理解所有历史写法；当前事实中包含版本号的行也可能被过滤，找不到时可用 include_history=true 或直接读原文件。

命中唯一末级 ATX 标题时，matched_section 和 next_action 的 sections 指向该小节。resolve 的 next_actions 按相同小节分组为 module_get_many。不唯一、没有标题或命中父节时仍返回摘要导航，不自动展开旁支。代码围栏内的伪标题不参与标题定位。

```json
{"query":"上传规则","project":"D:/my-project"}
```

需要历史时：

```json
{"query":"旧发布记录","project":"D:/my-project","include_history":true,"limit":20}
```

已知 ID 可直接 continuation_get，无需先搜索。默认 module_get 仅附未完成任务索引；full=true 附全部任务索引，但不内嵌任务正文。显式 sections/full 读取始终忠实返回原文，不偷偷过滤历史。archive 仍不参与当前 handoff 索引，需要时直接查原文件。

## STALE 后检查什么

resolve/module_status 的 change_summary 给出 added/modified/removed 文件数，无逐文件核验基线时是 null。changed_sources 沿用相同含义：null 表示未知，[] 表示已知没有变化。

需要缩小当前模块的检查位置时，调用 module_status：

```json
{"module_id":"context-router","project":"D:/vervision","review":true}
```

review_candidates 提供该模块正文中直接提及变更路径或文件名的位置，不默认扩展其他模块。每项有 module_id、heading、文档 path、最多五个 source_paths 和原因；最多五个候选，额外候选/路径用 omitted_count/omitted_source_count 表示。候选按文档顺序列出，不伪装成语义置信度排名。无标题的前言位置用 heading=null；重复标题须直接查看原文件。

候选明确注明未核实：文件名可能重名，没有候选也不代表没有影响。候选不包含正文，Agent 可选择相应 sections 或直接查看源文件。默认排除明确历史小节。旧基线没有逐文件数据时 baseline_known=false，不制造候选。

来源集合增删也可能是修改 sources 配置的结果，不一定是代码编辑。哈希不能恢复旧源码；工具不提供核验时的代码 diff，也不把 Git HEAD 当作核验基线。需要 Git diff 时由 Agent 明确比较基准。

STALE 不表示知识错误，FRESH 不表示知识正确。是否修改知识以及何时 verify，仍由 Agent 对照代码决定。
