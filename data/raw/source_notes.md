# 原始数据来源说明

## 抓取时间窗口

系统按运行时刻拉取各RSS源最新条目，默认每源最多抓取8条，再经去重、相关性过滤和多源均衡后保留最终样本。

## 来源与用途

1. Google News EN RSS（aggregator）
- 用途：覆盖英文媒体与综合新闻动态。
- 优点：更新快，覆盖面广。

2. Google News ZH RSS（aggregator）
- 用途：覆盖中文AI舆情与政策讨论。
- 优点：补充中文语境热点。

3. TechCrunch AI RSS（media）
- 用途：跟踪AI产品化与公司动态。
- 优点：创业/资本/产品发布密度高。

4. arXiv cs.AI RSS（research）
- 用途：跟踪学术研究与前沿方向。
- 优点：研究信号前置，适合趋势判断。

5. OpenAI News RSS（official）
- 用途：跟踪头部厂商官方发布。
- 优点：官方信息可信度高。

6. Hacker News AI RSS（social）
- 用途：跟踪社区讨论热度与早期信号。
- 优点：反映开发者社区兴趣变化。

## 数据质量策略

- AI相关性评分：`ai_relevance_score`（0-10）
- 最低相关性阈值：默认 `>=2`
- 噪声过滤：校园活动、泛通知等低价值条目降权/剔除
- 多源均衡：`min_per_source` 默认每源至少2条，再按时效补齐

## 兜底数据

- 文件：`data/raw/fallback_news.json`
- 触发条件：在线抓取不足目标样本数时自动补充。
- 目的：保障MVP在弱网络环境下仍可稳定生成日报。
