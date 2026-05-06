# AI舆情分析日报系统 - 项目说明文档

## 1. 项目目标

构建一个可运营的 AI 舆情分析日报系统：
- 自动采集多源AI信息
- 输出结构化洞察数据
- 生成可读日报与交互可视化
- 支持风险预警与趋势研判

## 1.1 文档受众与阅读路径

1. 评审方（看完整性）
- 先看：`docs/REQUIREMENTS_TRACEABILITY.md`
- 再看：`docs/PROJECT_DOCUMENTATION.md` 第3章与第3.2章

2. 开发方（看实现）
- 先看：`src/main.py`、`src/daily_update.py`
- 再看：`docs/SCHEMA_DESIGN.md`、`docs/AI_USAGE.md`

3. 运营方（看每日运行）
- 先看：`README.md` 的 3.3 自动更新
- 再看：`docs/MAINTENANCE_LOG.md`

## 2. 数据源与覆盖策略

## 2.1 数据源分类

- Aggregator: Google News EN / Google News ZH
- Media: TechCrunch AI
- Official: OpenAI News RSS
- Research: arXiv cs.AI
- Social: Hacker News AI RSS

配置文件：`configs/sources.json`

## 2.2 选择理由

- **广覆盖**：媒体、官方、研究、社区四类信号齐全。
- **高时效**：RSS可日更拉取，适配日报场景。
- **可复用**：来源参数化配置，便于扩展和A/B。

## 2.3 质量挑战

- 聚合源有转载、噪声和泛AI词污染。
- 不同来源文本密度差异大。
- 中英文混合场景存在编码与关键词召回差异。

## 3. 系统架构

1. **Ingest**：多源RSS采集（标准化来源元数据）
2. **Normalize**：HTML清洗、Unicode标准化、UTC时间统一
3. **Quality Gate**：AI相关性评分 + 噪声过滤
4. **Dedup**：URL + 标题归一化去重
5. **Diversity Select**：按来源均衡抽样（min_per_source）
6. **Extract**：结构化抽取（主题/事件/风险/机会/证据）
7. **Validate**：Schema required 字段校验
8. **Analyze**：影响分/热度分/趋势统计
9. **Present**：Markdown日报 + JSON日报 + 交互可视化

## 3.1 处理逻辑证明（结构化流程）

本系统通过显式流水线完成结构化处理与分析：

1. **采集与过滤**：按来源逐个采集，计算 `ai_relevance_score`，拦截噪声词（含校园活动类误报）。
2. **去重**：URL + 标题归一化双重去重，避免重复新闻堆叠影响判断。
3. **多源均衡抽样**：先满足 `min_per_source`，再按时效补齐，避免单一来源主导。
4. **分批抽取**：按 `extract_batch_size` 对样本分批处理，支持批次级追踪与回放。
5. **结构化抽取**：输出 `topic_tags/entities/event_type/sentiment/risk_tags/opportunity_tags/evidence` 等字段。
6. **质量校验**：检查 schema required 字段、`extract_confidence`、`no_topic`、`schema_error_count`。
7. **分析与评分**：基于结构化字段计算 `impact_score/hot_score`，生成热点与趋势。

可核验产物：
- 原始样本：`data/raw/raw_news.jsonl`
- 结构化结果：`data/processed/structured_news.jsonl`
- 质量指标：`outputs/run_log.json`（含 `no_topic`、`llm_batches`、`rule_batches`）
- 运行日志：`outputs/pipeline.log`（含分批进度和告警）

## 3.2 处理逻辑审计清单（步骤-输入-输出-校验）

1. 采集（Ingest）
- 输入：`configs/sources.json` 来源配置
- 输出：采集到的源数据对象（title/summary/url/time/source）
- 校验：每源扫描/保留/过滤数量写入 `outputs/pipeline.log`

2. 清洗与标准化（Normalize）
- 输入：原始 RSS 字段
- 输出：清洗后的 `title/summary/published_at`
- 校验：统一 UTF-8、HTML 去噪、UTC 时间格式

3. 相关性过滤与噪声拦截（Quality Gate）
- 输入：清洗后文本
- 输出：带 `ai_relevance_score/ai_relevance_reason` 的样本
- 校验：低相关和噪声样本被剔除；过滤原因在日志可追踪

4. 去重与均衡（Dedup + Diversity Select）
- 输入：多源候选样本
- 输出：去重后、来源均衡后的候选集
- 校验：URL/标题去重统计、`min_per_source` 约束生效

5. 分批结构化抽取（Batch Extract）
- 输入：候选样本（按 `extract_batch_size` 分批）
- 输出：结构化记录（topic/event/entity/risk/opportunity/evidence）
- 校验：日志中可看到 batch start/done 进度；`llm_batches/rule_batches` 入 `run_log.json`

6. 结果校验（Validate）
- 输入：结构化记录
- 输出：通过 schema 校验的数据集
- 校验：`schema_error_count/no_topic/low_confidence` 写入 `outputs/run_log.json`

7. 报告与可视化（Analyze + Present）
- 输入：校验通过的结构化数据
- 输出：`daily_report.md/json` + `visualization.html`
- 校验：产物路径、记录数量、质量指标完整落盘

## 4. 关键设计决策

## 4.1 数据治理优先于“摘要漂亮”

核心目标是形成可计算结构化数据，因此加入：
- `ai_relevance_score`
- `source_type`
- `source_weight`
- `source_region`
- `evidence`

## 4.2 相关性评分与噪声过滤

- 关键词分层：强AI词、弱AI词、噪声词
- 默认阈值：`min_relevance_score=2`
- 噪声策略：若噪声命中且缺少强AI信号，则剔除

## 4.3 多源均衡策略

- 先按来源保证最低配额（`min_per_source`）
- 再按发布时间补齐至目标样本数
- 避免单一来源“刷屏”导致分析偏置

## 5. 评分逻辑

## 5.1 Impact Score

综合因素：
- 发布时间新鲜度
- 来源权重
- 主题覆盖度
- 事件类型
- 情绪影响

## 5.2 Hot Score

`hot = 0.35*impact + 0.25*source_weight + 0.20*recency + 0.20*topic_hint`

## 6. AI 使用方式

当前支持 `rule/hybrid/llm` 三种抽取模式：
- `rule`：默认稳态，适合离线和无密钥环境
- `hybrid`：在线LLM优先，失败自动回退规则（推荐）
- `llm`：强制尝试LLM，失败仍保底回退，避免产物中断

- 抽取Prompt：`prompts/extract_prompt.md`
- 分析Prompt：`prompts/analysis_prompt.md`
- 运行参数：`--extract-mode --llm-model --llm-timeout-sec`
- 环境变量：`OPENAI_API_KEY`

## 7. 可观测性与调试

日志文件：`outputs/pipeline.log`

覆盖指标：
- 每源扫描/保留/过滤数量
- 低相关性与噪声拦截数量
- 去重统计
- 抽取质量（低置信度、无主题）
- schema校验结果
- 产物写出与总耗时

## 7.1 常见故障与处理

1. 抓取源超时
- 现象：`collector_logs` 出现 `[WARN] source: timeout`
- 处理：重试；必要时提高 `per_source_limit` 或启用 fallback 兜底

2. 无法命中在线LLM
- 现象：`Hybrid LLM extraction failed`，`llm_batches=0`
- 处理：检查 `OPENAI_API_KEY`，无密钥时允许规则降级继续产出

3. 主题标签缺失上升
- 现象：`quality.no_topic` 增大
- 处理：扩展 `TOPIC_RULES` 和 fallback 推断词典，复跑并观察回落

4. 样本不足
- 现象：`Insufficient news after collection`
- 处理：降低过滤阈值、提升来源抓取上限、检查源可用性

## 8. 输出产物

- 原始数据：`data/raw/raw_news.jsonl`
- 结构化数据：`data/processed/structured_news.jsonl`
- 日报（人读）：`outputs/daily_report.md`
- 日报（机读）：`outputs/daily_report.json`
- 日报对比（人读）：`outputs/daily_comparison.md`
- 日报对比（机读）：`outputs/daily_comparison.json`
- 可视化：`outputs/visualization.html`
- 运行摘要：`outputs/run_log.json`
- 调试日志：`outputs/pipeline.log`

## 8.1 自动更新与历史对比

新增脚本：`src/daily_update.py`

能力：
- 执行当日数据更新与日报生成
- 自动归档至 `outputs/history/run_YYYYMMDD_HHMMSS/`
- 自动与上一次快照做差异对比（样本规模、主题分布、来源分布、Top事件变化、story churn）

## 8.2 版本与变更治理

1. 文档变更入口
- `CHANGELOG.md`：功能级变更
- `docs/MAINTENANCE_LOG.md`：运维与质量变更

2. 数据与报告版本线索
- `outputs/run_log.json`：每次运行参数、质量指标、产物路径
- `outputs/history/`：历史快照可回溯

3. 对比产物
- `outputs/daily_comparison.md/json`：今日 vs 上次差异审计

## 9. 已知局限与演进方向

- 实体识别在rule模式下仍以轻量规则为主，建议增加NER或提升LLM覆盖率。
- 去重可引入向量语义聚类增强跨源识别。
- 风险识别可引入事件级规则库与行业词典。
- 可接入定时任务与告警通道（邮件/IM）实现准生产化。
