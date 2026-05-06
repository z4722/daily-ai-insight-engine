# Daily AI Insight Engine

一个可运行的 AI 舆情分析日报系统（MVP+）：从多源新闻采集开始，完成结构化抽取、趋势分析、可视化输出与调试日志落盘。

## 1. 项目结构

```text
.
├─ .editorconfig
├─ .github/
│  └─ workflows/
│     └─ ci.yml
├─ CHANGELOG.md
├─ pyproject.toml
├─ configs/
│  ├─ sources.json
│  └─ schema.json
├─ data/
│  ├─ raw/
│  │  ├─ fallback_news.json
│  │  ├─ raw_news.jsonl
│  │  └─ source_notes.md
│  └─ processed/
│     └─ structured_news.jsonl
├─ docs/
│  ├─ ENTERPRISE_DOC_BENCHMARK.md
│  ├─ PROJECT_DOCUMENTATION.md
│  ├─ SCHEMA_DESIGN.md
│  ├─ AI_USAGE.md
│  ├─ MAINTENANCE_LOG.md
│  └─ REQUIREMENTS_TRACEABILITY.md
├─ outputs/
│  ├─ daily_report.md
│  ├─ daily_report.json
│  ├─ daily_comparison.md
│  ├─ daily_comparison.json
│  ├─ visualization.html
│  ├─ run_log.json
│  └─ pipeline.log
│  └─ history/
├─ prompts/
│  ├─ extract_prompt.md
│  └─ analysis_prompt.md
└─ src/
   ├─ daily_update.py
   ├─ main.py
   └─ smoke_test.py
└─ tests/
   └─ test_daily_update.py
```

## 2. 运行环境

- Python 3.11+
- 依赖：标准库（MVP默认无第三方包）

## 3. 快速开始

### 3.1 运行主流程

```bash
python src/main.py --max-items 20 --per-source-limit 8 --min-required 10 --min-relevance-score 2 --min-per-source 2 --extract-batch-size 5 --extract-mode hybrid --log-level INFO
```

参数说明：
- `--min-relevance-score`：AI相关性最低分（0-10）
- `--min-per-source`：每个来源至少保留条数（用于多源均衡）
- `--extract-batch-size`：结构化抽取批大小（显式分批处理）
- `--extract-mode`：抽取模式，`rule | hybrid | llm`
- `--llm-model`：在线抽取模型名（默认 `gpt-4.1-mini`）
- `--llm-timeout-sec`：每个LLM批次超时秒数

模式说明：
- `rule`：仅规则抽取（不依赖API Key）
- `hybrid`：优先在线LLM抽取，失败自动回退规则
- `llm`：强制尝试LLM抽取，失败也会记录告警并回退规则以保证产物可用

如需启用在线LLM抽取，请先设置环境变量：

```bash
# PowerShell
$env:OPENAI_API_KEY="your_key"
```

### 3.2 运行冒烟测试

```bash
python src/smoke_test.py
```

测试通过标志：`SMOKE_TEST_PASS`

离线单元测试（不依赖外部新闻源）：

```bash
python -m unittest -v tests.test_daily_update
```

### 3.3 每日自动更新 + 与上一日报对比

```bash
python src/daily_update.py --max-items 20 --per-source-limit 8 --min-required 10 --min-relevance-score 2 --min-per-source 2 --extract-batch-size 5 --extract-mode hybrid --log-level INFO
```

脚本行为：
- 先执行当日采集与日报生成
- 自动归档到 `outputs/history/run_YYYYMMDD_HHMMSS/`
- 自动与上一快照对比，并输出：
  - `outputs/daily_comparison.md`
  - `outputs/daily_comparison.json`

可选参数：
- `--snapshot-name`：手动指定快照名
- `--no-compare`：仅更新与归档，不做对比
- `--history-dir`：自定义历史归档目录

Windows 定时任务示例（每天 09:00）：

```powershell
schtasks /Create /SC DAILY /ST 09:00 /TN "DailyAIInsightUpdate" /TR "powershell -NoProfile -ExecutionPolicy Bypass -Command \"cd C:\Users\xwhhh\Desktop\test; python src\daily_update.py --extract-mode hybrid --max-items 20 --log-level INFO\"" /F
```

## 4. 输出产物

- 原始数据：`data/raw/raw_news.jsonl`
- 结构化数据：`data/processed/structured_news.jsonl`
- 日报（人读）：`outputs/daily_report.md`
- 日报（机读）：`outputs/daily_report.json`
- 可视化：`outputs/visualization.html`
- 运行日志：`outputs/pipeline.log`
- 运行摘要：`outputs/run_log.json`

## 5. 产品级增强（相较基础MVP）

- 来源分层：aggregator/media/official/social/research
- 来源权重：source_weight进入impact/hot score计算
- 相关性评分：ai_relevance_score过滤低价值噪音
- 噪声拦截：校园活动/泛通知类内容降权或过滤
- 数据均衡：min_per_source保障来源多样性
- 分批抽取：extract_batch_size体现显式批处理
- 在线抽取链路：支持rule/hybrid/llm三模式与批次级降级
- 编码修复：中文乱码模式自动尝试修复
- no_topic优化：扩展主题词典 + 兜底推断 + 校园噪声过滤
- 可视化交互：筛选/排序/动态图表/移动端适配

## 5.1 处理逻辑（明确非摘要拼接）

系统执行的是“采集-清洗-过滤-去重-分批抽取-校验-分析-可视化”的流水线，不是简单摘要拼接。  
可直接检查：
- 结构化字段：`data/processed/structured_news.jsonl`
- 分批与质量日志：`outputs/pipeline.log`、`outputs/run_log.json`

## 6. 调试说明

日志级别支持：`DEBUG / INFO / WARNING / ERROR`

示例：

```bash
python src/main.py --log-level DEBUG
```

已记录关键节点：
- 采集阶段（每源扫描/保留/过滤数量与耗时）
- 去重统计（URL/标题重复数）
- 结构化抽取进度与质量告警
- Schema必填字段校验
- 报告与可视化文件写出状态

## 6.1 工程质量规范

- 代码风格配置：`pyproject.toml`（Ruff 规则）
- 编辑器统一配置：`.editorconfig`
- CI 校验：`.github/workflows/ci.yml`
  - 编译检查：`py_compile`
  - 离线单元测试：`tests/test_daily_update.py`

## 7. 阅读文档

- 大厂文档对标：`docs/ENTERPRISE_DOC_BENCHMARK.md`
- 系统与流程：`docs/PROJECT_DOCUMENTATION.md`
- Schema设计：`docs/SCHEMA_DESIGN.md`
- AI使用策略：`docs/AI_USAGE.md`
- 维护日志：`docs/MAINTENANCE_LOG.md`
- 需求追踪矩阵：`docs/REQUIREMENTS_TRACEABILITY.md`
- 变更日志：`CHANGELOG.md`
- Prompt模板：`prompts/extract_prompt.md`、`prompts/analysis_prompt.md`

## 8. 文档质量门禁（提交前）

1. 处理逻辑是否可审计：清洗、分批、校验是否有明确步骤与证据文件。
2. 结构化是否充分：是否包含 topic/event/entity/risk/opportunity/evidence，而非摘要拼接。
3. 质量指标是否可追踪：`no_topic`、`schema_error_count`、`llm_batches`、`rule_batches`。
4. 运行与排障是否可执行：是否提供一键命令、日志路径、失败恢复路径。
5. 更新机制是否闭环：是否支持自动更新、历史快照、与上一日报自动对比。
