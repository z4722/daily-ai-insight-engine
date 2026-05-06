# Schema设计说明

Schema文件：`configs/schema.json`（版本 1.1.0）

## 1. 设计目标

把新闻文本转为可计算、可追踪、可复核的数据结构，支撑：
- 热点排序
- 趋势统计
- 风险机会识别
- 日报自动生成
- 数据质量治理

## 2. 字段分层

### 2.1 原始事实层

- `title`
- `source`
- `url`
- `published_at`
- `raw_summary`

作用：保留事实上下文，便于回溯与证据核验。

### 2.2 来源治理层

- `source_type`
- `source_weight`
- `source_region`

作用：支撑来源分层、可信度加权与多源均衡策略。

### 2.3 相关性质量层

- `ai_relevance_score`
- `ai_relevance_reason`

作用：过滤泛AI噪声，提升样本信息密度。

### 2.4 语义抽取层

- `topic_tags`
- `entities`
- `event_type`
- `sentiment`

作用：把非结构化文本转成可统计语义标签。

### 2.5 决策支持层

- `impact_score`
- `risk_tags`
- `opportunity_tags`
- `extract_confidence`

作用：支持排序、预警与人工复核优先级。

### 2.6 证据层

- `evidence`

作用：让结论可解释，避免黑箱总结。

## 3. 关键设计原则

- **唯一性**：`id = hash(url + title)`，用于去重和追踪。
- **可解释**：保留 evidence，报告结论可回溯到原始文本。
- **可扩展**：topic/risk/opportunity为数组，便于扩展标签体系。
- **可治理**：来源权重 + 相关性评分共同约束数据质量。
- **可校验**：运行时检查 required 字段是否齐全。

## 4. 运行时校验

主流程读取 `schema.required` 并检查每条结构化记录是否缺字段。
校验结果输出：
- `outputs/run_log.json` -> `quality.schema_error_count`
- `outputs/pipeline.log` -> WARNING

## 5. 后续扩展建议

- 新增 `region_impact`（区域影响等级）
- 新增 `market_segment`（ToC/ToB/Developer）
- 新增 `fact_check_status`（人工审核状态）
- 新增 `novelty_score`（与近7日语义差异）
