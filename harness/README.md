# Minimal Harness Demo

This harness runs a deterministic offline evaluation for the Daily AI Insight Engine.

## What it does

1. Loads a fixed JSONL dataset from `harness/datasets/demo_input.jsonl`.
2. Reuses extraction and analysis functions from `src/main.py`.
3. Applies assertion checks from `harness/config/assertions_demo.json`.
4. Writes reproducible artifacts under `harness/runs/run_YYYYMMDD_HHMMSS/`.

## Run

```bash
python harness/run_demo_harness.py
```

## Optional flags

```bash
python harness/run_demo_harness.py \
  --extract-mode rule \
  --extract-batch-size 4 \
  --dataset harness/datasets/demo_input.jsonl \
  --assertions-config harness/config/assertions_demo.json
```

For online semantic extraction:

```powershell
$env:OPENAI_API_KEY="your_key"
python harness/run_demo_harness.py --extract-mode hybrid
```

## Output files

Each run writes:

- `raw_news.jsonl`
- `structured_news.jsonl`
- `daily_report.md`
- `daily_report.json`
- `visualization.html`
- `harness_result.json`
- `harness_result.md`

## Assertions in this demo

- input count range
- top event count range
- schema errors upper bound
- no-topic upper bound
- average confidence lower bound
- source diversity lower bound
- low-confidence ratio upper bound
