# AI使用与Prompt策略

## 1. 使用场景

当前系统已支持三种抽取模式：
- `rule`：仅规则抽取，保证无API密钥可运行
- `hybrid`：优先LLM，失败自动回退规则
- `llm`：强制尝试LLM，失败记录告警并回退规则

生产化建议采用规则 + LLM混合：
- 规则层负责质量闸门（相关性、去重、字段兜底）
- LLM层负责复杂语义理解（深层事件、实体消歧、归因分析）

## 2. Prompt模板

- 抽取模板：`prompts/extract_prompt.md`
- 分析模板：`prompts/analysis_prompt.md`

## 3. 分批处理策略

采用分批处理策略，推荐：
- 每批3-5条新闻
- 每条输出独立schema对象
- 批次间做结果校验与重试

## 4. 质量闸门（模型前/后）

### 4.1 模型前

- `ai_relevance_score` 过滤低价值样本
- 噪声关键词策略拦截泛AI条目
- 多源均衡控制单源偏置

### 4.2 模型后

- JSON格式校验
- schema required字段校验
- evidence数量校验（2-3条）
- confidence阈值校验（<0.60标记复核）

## 5. 错误处理

### 5.1 输出非JSON

- 重试并追加约束："Only return valid JSON"。
- 若连续失败，回退规则抽取路径。

### 5.2 字段缺失

- 根据schema定位缺失字段。
- 对可规则补齐字段（language/time/id/source metadata）进行回填。

### 5.3 幻觉风险

- 仅依据输入文本生成结论。
- 每条结论必须附 evidence。
- 不确定项降低 confidence。

## 6. 与当前代码衔接

当前代码已具备：
- 来源分层与权重
- 相关性评分与噪声过滤
- Schema加载与required字段检查
- 结构化产物与日志落盘
- 在线LLM抽取接口（OpenAI Chat Completions）
- 批次级引擎使用统计：`llm_batches` / `rule_batches`
- `no_topic` 质量指标与告警

启用在线抽取示例：

```bash
# PowerShell
$env:OPENAI_API_KEY="your_key"
python src/main.py --extract-mode hybrid --llm-model gpt-4.1-mini --extract-batch-size 5 --log-level INFO
```
