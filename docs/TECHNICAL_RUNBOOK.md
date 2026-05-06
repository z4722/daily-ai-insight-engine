# 技术运行手册（参数、更新、可视化）

本文用于日常开发和运维，聚焦三件事：
1. 可修改参数
2. 每日更新方式
3. 可视化前端打开方式

## 1. 主流程参数（`src/main.py`）

运行命令示例：

```bash
python src/main.py --max-items 20 --per-source-limit 8 --min-required 10 --min-relevance-score 2 --min-per-source 2 --extract-batch-size 5 --extract-mode hybrid --log-level INFO
```

参数说明：
- `--max-items`：最终样本条数上限（默认 `20`）
- `--per-source-limit`：每个来源抓取上限（默认 `8`）
- `--min-required`：继续执行所需最小样本数（默认 `10`）
- `--min-relevance-score`：AI相关性阈值（`0-10`，默认 `2`）
- `--min-per-source`：来源均衡保底条数（默认 `2`）
- `--extract-batch-size`：结构化抽取批次大小（默认 `5`）
- `--extract-mode`：抽取模式（`rule | hybrid | llm`，默认 `hybrid`）
- `--llm-model`：在线抽取模型名（默认 `gpt-4.1-mini`）
- `--llm-timeout-sec`：单批 LLM 超时秒数（默认 `45`）
- `--log-level`：日志级别（`DEBUG/INFO/WARNING/ERROR`）

## 2. 每日自动更新（`src/daily_update.py`）

运行命令示例：

```bash
python src/daily_update.py --max-items 20 --extract-mode hybrid --log-level INFO
```

脚本动作：
1. 执行当日采集与日报生成
2. 归档到 `outputs/history/run_YYYYMMDD_HHMMSS/`
3. 生成与上一次快照对比报告

常用参数：
- `--snapshot-name`：手动指定快照名
- `--history-dir`：自定义归档目录
- `--no-compare`：仅更新与归档

Windows 定时任务示例（每天 09:00）：

```powershell
schtasks /Create /SC DAILY /ST 09:00 /TN "DailyAIInsightUpdate" /TR "powershell -NoProfile -ExecutionPolicy Bypass -Command \"cd C:\Users\xwhhh\Desktop\test; python src\daily_update.py --extract-mode hybrid --max-items 20 --log-level INFO\"" /F
```

## 3. 可视化前端如何打开

可视化文件输出路径：
- `outputs/visualization.html`

打开方式 A（直接打开文件）：

```powershell
Invoke-Item outputs\visualization.html
```

打开方式 B（本地 HTTP 服务）：

```powershell
python -m http.server 8000
```

然后访问：
- `http://localhost:8000/outputs/visualization.html`

## 4. 更新后重点核对文件

1. 数据文件
- `data/raw/raw_news.jsonl`
- `data/processed/structured_news.jsonl`

2. 日报与可视化
- `outputs/daily_report.md`
- `outputs/daily_report.json`
- `outputs/visualization.html`

3. 运行与质量
- `outputs/run_log.json`
- `outputs/pipeline.log`
- `outputs/daily_comparison.md`
- `outputs/daily_comparison.json`

## 5. 参数调优建议

1. 提高相关新闻密度：
- 调大 `--min-relevance-score`（如 `3`）

2. 提高来源覆盖：
- 调大 `--per-source-limit`（如 `10`）
- 维持 `--min-per-source=2` 或更高

3. 控制运行时间：
- 降低 `--max-items`
- 调整 `--extract-batch-size`（如 `4-6`）
