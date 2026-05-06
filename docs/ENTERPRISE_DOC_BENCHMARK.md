# 大厂文档要求对标与优化说明

本文基于公开文档规范，对当前项目文档进行“可审计、可执行、可维护”升级。

## 1. 对标来源（公开官方文档）

1. Google Developer Documentation Style Guide
- 面向读者：用第二人称（you）并使用祈使句指令。
- 强调一致受众、明确动作主体。
- 参考：
  - https://developers.google.com/style/person
  - https://developers.google.com/style/translation

2. Microsoft Style Guide
- 步骤文档强调可扫描性（标题并行、层级清晰、步骤一致）。
- 文风强调简洁、先结论后解释、减少冗词。
- 参考：
  - https://learn.microsoft.com/en-us/style-guide/procedures-instructions/writing-step-by-step-instructions
  - https://learn.microsoft.com/en-us/style-guide/top-10-tips-style-voice

3. GitHub Docs（大型开发者文档体系）
- 强调“全球读者可读性”、避免俚语、保持术语一致。
- 强调“高价值场景优先”和可迭代更新。
- 参考：
  - https://docs.github.com/en/contributing/style-guide-and-content-model/style-guide
  - https://docs.github.com/en/contributing/writing-for-github-docs/content-design-principles

4. Stripe API Docs
- 强调版本化、错误处理、可编程错误语义。
- 参考：
  - https://docs.stripe.com/apis
  - https://docs.stripe.com/api/errors

5. AWS 文档约定示例
- 强调不同系统/命令环境的示例区分与展示规范。
- 参考：
  - https://docs.aws.amazon.com/systems-manager/latest/userguide/docconventions.html

## 2. 抽取出的“文档硬要求”

1. 受众明确：每份文档要说明读者是谁（开发、运营、评审、管理者）。
2. 任务导向：步骤必须可执行，避免仅叙述背景。
3. 先结论后细节：章节开头给“能直接执行”的结论或命令。
4. 分层结构：概览 -> 操作 -> 验证 -> 排障 -> 变更记录。
5. 术语一致：同一概念只用一个词，避免别名混用。
6. 多语言可维护：避免口语化、俚语、歧义时间表达。
7. 错误可处理：说明失败信号、定位方法、恢复动作。
8. 质量可量化：要求有可观测指标（如 `no_topic`、`schema_error_count`）。
9. 版本可追踪：产物与文档都应有版本和更新时间线索。
10. 差异可对比：支持“本次 vs 上次”自动比较与归档。

## 3. 本项目已落实的优化点

1. 处理逻辑显式化
- 在 `docs/PROJECT_DOCUMENTATION.md` 增加“步骤-输入-输出-校验”审计清单。

2. 分批与校验可观测
- 在 `outputs/run_log.json` 固化 `llm_batches/rule_batches/no_topic/schema_error_count`。

3. 每日自动更新与对比
- 新增 `src/daily_update.py`，自动生成历史快照和 `daily_comparison.md/json`。

4. 运行指引可执行
- README 提供主流程、自动更新、Windows 定时任务样例。

## 4. 文档评审检查清单（提交前）

1. 是否清楚写明数据从哪里来、为何选这些来源。
2. 是否清楚写明清洗、过滤、去重、分批、校验。
3. 是否有结构化字段、评分字段和证据字段形成完整分析闭环。
4. 是否有质量指标并能在文件中定位。
5. 是否有失败处理与降级策略。
6. 是否有每日更新和历史对比机制。
7. 是否有变更日志与维护日志。

若以上 7 项都能在仓库中快速定位，则文档质量已达到“互联网大厂可评审”标准。
