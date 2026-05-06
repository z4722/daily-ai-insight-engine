from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_DIR = ROOT / "outputs"
CONFIG_FILE = ROOT / "configs" / "sources.json"
SCHEMA_FILE = ROOT / "configs" / "schema.json"
FALLBACK_FILE = ROOT / "data" / "raw" / "fallback_news.json"
EXTRACT_PROMPT_FILE = ROOT / "prompts" / "extract_prompt.md"
LOG_FILE = OUTPUT_DIR / "pipeline.log"

LOGGER = logging.getLogger("daily_ai_insight")

AI_KEYWORDS = [
    "ai",
    "artificial intelligence",
    "machine learning",
    "llm",
    "model",
    "agent",
    "openai",
    "anthropic",
    "google deepmind",
    "nvidia",
    "人工智能",
    "大模型",
    "生成式",
    "机器学习",
    "智能体",
]

AI_STRONG_KEYWORDS = [
    "openai",
    "anthropic",
    "deepmind",
    "meta ai",
    "copilot",
    "chatgpt",
    "claude",
    "gemini",
    "llm",
    "foundation model",
    "multi-modal",
    "transformer",
    "inference",
    "agent",
    "open source model",
    "人工智能",
    "大模型",
    "推理模型",
    "多模态",
    "智能体",
    "算力",
]

AI_NOISE_KEYWORDS = [
    "招生",
    "校友",
    "讲座",
    "心理",
    "表彰",
    "通知",
    "学院活动",
    "毕业",
    "团委",
    "campus",
    "admission",
    "alumni",
    "scholarship",
    "classroom",
    "student activity",
]

CAMPUS_CONTEXT_KEYWORDS = [
    "学院",
    "大学",
    "新闻网",
    "校园",
    "讲座",
    "培训",
    "学生",
    "心理",
    "campus",
    "student",
    "faculty",
    "undergraduate",
    "postgraduate",
]

AI_TECH_SIGNAL_KEYWORDS = [
    "大模型",
    "模型",
    "llm",
    "gpt",
    "agent",
    "benchmark",
    "arxiv",
    "dataset",
    "inference",
    "gpu",
    "芯片",
    "推理",
    "训练",
    "发布",
    "开源",
    "论文",
    "research",
    "api",
    "sdk",
    "framework",
    "融资",
    "投资",
    "监管",
    "policy",
]

TOPIC_RULES = {
    "Model Release": [
        "launch",
        "release",
        "announce",
        "model",
        "gpt",
        "llm",
        "foundation model",
        "multimodal",
        "api update",
        "发布",
        "推出",
        "模型",
        "开源模型",
        "推理模型",
    ],
    "Application": [
        "product",
        "app",
        "workflow",
        "deployment",
        "copilot",
        "automation",
        "assistant",
        "agent",
        "enterprise",
        "restaurant",
        "registry",
        "job",
        "workforce",
        "应用",
        "落地",
        "场景",
        "企业",
        "助手",
        "自动化",
        "就业",
        "岗位",
    ],
    "Policy": [
        "policy",
        "regulation",
        "law",
        "compliance",
        "governance",
        "rules",
        "united nations",
        "international cooperation",
        "capacity building",
        "framework",
        "监管",
        "政策",
        "法规",
        "治理",
        "合规",
        "审查",
        "联合国",
        "国际合作",
        "能力建设",
        "框架",
    ],
    "Research": [
        "paper",
        "arxiv",
        "benchmark",
        "research",
        "dataset",
        "evaluation",
        "study",
        "researchers",
        "研究",
        "论文",
        "基准",
        "实验",
        "评测",
    ],
    "Capital": [
        "funding",
        "acquisition",
        "investment",
        "ipo",
        "valuation",
        "angel round",
        "series",
        "融资",
        "投资",
        "并购",
        "估值",
    ],
    "Infrastructure": [
        "chip",
        "gpu",
        "cloud",
        "inference",
        "infra",
        "datacenter",
        "compute",
        "latency",
        "token cost",
        "算力",
        "芯片",
        "云",
        "数据中心",
        "推理",
    ],
    "Safety": [
        "safety",
        "risk",
        "security",
        "alignment",
        "misalignment",
        "red team",
        "harmful",
        "安全",
        "风险",
        "治理",
        "对齐",
    ],
}

EVENT_RULES = {
    "Release": ["launch", "release", "announce", "发布", "推出"],
    "Partnership": ["partner", "collaboration", "joint", "合作", "联手"],
    "Funding": ["funding", "raise", "investment", "融资", "投资"],
    "Policy": ["policy", "regulation", "law", "监管", "政策", "法规"],
    "Incident": ["outage", "ban", "lawsuit", "breach", "中断", "封禁", "诉讼", "泄露"],
    "Research": ["paper", "arxiv", "benchmark", "研究", "论文"],
}

SENTIMENT_POS = ["growth", "record", "improve", "breakthrough", "adoption", "增长", "突破", "提升"]
SENTIMENT_NEG = ["risk", "ban", "fine", "lawsuit", "concern", "drop", "outage", "风险", "罚款", "诉讼", "下滑"]

RISK_RULES = {
    "Regulatory": ["regulation", "policy", "ban", "监管", "禁令", "合规"],
    "Safety": ["safety", "alignment", "security", "hallucination", "安全", "幻觉", "偏见"],
    "Commercial": ["cost", "price", "competition", "margin", "成本", "竞争", "利润"],
}

OPPORTUNITY_RULES = {
    "Enterprise Adoption": ["enterprise", "workflow", "productivity", "企业", "提效", "自动化"],
    "Developer Tooling": ["api", "sdk", "agent", "framework", "开发者", "工具链"],
    "Infrastructure Demand": ["gpu", "cloud", "inference", "chip", "算力", "云"],
    "Industry Vertical": ["healthcare", "finance", "education", "医疗", "金融", "教育"],
}

SOURCE_WEIGHTS = {
    "Google News EN": 0.78,
    "Google News ZH": 0.78,
    "TechCrunch AI": 0.84,
    "arXiv cs.AI": 0.86,
}

SOURCE_TYPE_DEFAULT_WEIGHT = {
    "aggregator": 0.76,
    "media": 0.82,
    "official": 0.88,
    "social": 0.74,
    "research": 0.86,
    "fallback": 0.70,
}

DEFAULT_LLM_MODEL = "gpt-4.1-mini"


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def configure_console_encoding() -> None:
    # Keep Chinese/English mixed output readable on Windows terminals.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        # Some environments don't support reconfigure(); ignore safely.
        pass


def setup_logger(log_level: str = "INFO") -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    LOGGER.setLevel(level)
    LOGGER.propagate = False

    if LOGGER.handlers:
        for handler in list(LOGGER.handlers):
            LOGGER.removeHandler(handler)

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)

    LOGGER.addHandler(file_handler)
    LOGGER.addHandler(stream_handler)


def load_sources() -> list[dict[str, Any]]:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"Missing config file: {CONFIG_FILE}")
    LOGGER.info("Loading source config: %s", CONFIG_FILE)
    with CONFIG_FILE.open("r", encoding="utf-8-sig") as f:
        payload = json.load(f)
    raw_sources = payload.get("sources", [])
    sources: list[dict[str, Any]] = []
    disabled_count = 0
    for source in raw_sources:
        if not source.get("enabled", True):
            disabled_count += 1
            continue
        source_ctx = build_source_context(source)
        if not source_ctx["name"] or not source_ctx["url"]:
            LOGGER.warning("Skip invalid source config: %s", source)
            continue
        sources.append(source_ctx)
    LOGGER.info("Loaded %d enabled sources (disabled=%d)", len(sources), disabled_count)
    return sources


def load_schema() -> dict[str, Any]:
    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(f"Missing schema file: {SCHEMA_FILE}")
    LOGGER.info("Loading schema config: %s", SCHEMA_FILE)
    with SCHEMA_FILE.open("r", encoding="utf-8-sig") as f:
        schema = json.load(f)
    version = schema.get("version", "unknown")
    required = schema.get("required", [])
    LOGGER.info("Loaded schema version=%s required_fields=%d", version, len(required))
    return schema


def load_extract_prompt() -> str:
    default_prompt = (
        "You are an AI news information extraction engine. "
        "For each input item, return structured fields only in JSON format."
    )
    if not EXTRACT_PROMPT_FILE.exists():
        LOGGER.warning("Extract prompt file not found, fallback to default prompt")
        return default_prompt
    try:
        prompt_text = EXTRACT_PROMPT_FILE.read_text(encoding="utf-8-sig").strip()
        return prompt_text or default_prompt
    except Exception as exc:
        LOGGER.warning("Failed to read extract prompt file, fallback to default: %s", exc)
        return default_prompt


def strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", text or "")
    clean = unescape(clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def normalize_text(text: str) -> str:
    # Normalize width/compat forms first for stable keyword matching.
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def maybe_fix_mojibake(text: str) -> str:
    if not text:
        return ""
    # Common pattern: UTF-8 bytes decoded by GBK, e.g. "鏃朵唬" instead of "时代".
    # Only apply when suspicious markers are dense enough.
    suspicious_markers = ["鏃", "锛", "鈥", "銆", "鍚", "鐨", "闂", "浜", "浠"]
    marker_hits = sum(1 for marker in suspicious_markers if marker in text)
    if marker_hits == 0:
        return text
    try:
        repaired = text.encode("gbk", errors="ignore").decode("utf-8", errors="ignore")
        if len(repaired) >= max(2, int(len(text) * 0.45)):
            return repaired
    except Exception:
        return text
    return text


def build_source_context(source: dict[str, Any]) -> dict[str, Any]:
    name = source.get("name", "unknown")
    source_type = source.get("source_type", "aggregator")
    configured_weight = source.get("source_weight")
    if configured_weight is None:
        configured_weight = SOURCE_WEIGHTS.get(name, SOURCE_TYPE_DEFAULT_WEIGHT.get(source_type, 0.74))
    try:
        source_weight = float(configured_weight)
    except Exception:
        source_weight = 0.74
    source_weight = max(0.0, min(source_weight, 1.0))
    return {
        "name": name,
        "url": source.get("url", ""),
        "source_type": source_type,
        "source_weight": source_weight,
        "source_region": source.get("source_region", "global"),
        "always_ai": bool(source.get("always_ai", False)),
    }


def parse_date(raw: str | None) -> datetime:
    if not raw:
        LOGGER.debug("Date missing, fallback to now")
        return datetime.now(timezone.utc)
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        LOGGER.debug("RFC date parse failed: %s", raw)
    for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    LOGGER.debug("All date parsers failed, fallback to now: %s", raw)
    return datetime.now(timezone.utc)


def get_child_text(node: ET.Element, names: list[str]) -> str:
    for name in names:
        child = node.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def get_link(node: ET.Element) -> str:
    link = get_child_text(node, ["link", "{http://www.w3.org/2005/Atom}link"])
    if link:
        return link
    atom_link = node.find("{http://www.w3.org/2005/Atom}link")
    if atom_link is not None:
        href = atom_link.attrib.get("href")
        if href:
            return href
    for child in node.findall("{http://www.w3.org/2005/Atom}link"):
        href = child.attrib.get("href")
        if href:
            return href
    return ""


def fetch_rss(source: dict[str, Any], per_source_limit: int, min_relevance_score: int) -> list[dict[str, Any]]:
    source_name = source["name"]
    url = source["url"]
    source_type = source["source_type"]
    source_weight = source["source_weight"]
    source_region = source["source_region"]
    always_ai = source["always_ai"]
    LOGGER.info("Fetching RSS: source=%s limit=%d", source_name, per_source_limit)
    start = time.perf_counter()
    req = urllib.request.Request(url, headers={"User-Agent": "DailyAIInsightEngine/0.1"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        content = resp.read()
        status = getattr(resp, "status", "unknown")
        LOGGER.debug("HTTP response: source=%s status=%s bytes=%d", source_name, status, len(content))

    root = ET.fromstring(content)
    items = root.findall(".//item")
    if not items:
        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    if not items:
        LOGGER.warning("No RSS items found: source=%s", source_name)

    results: list[dict[str, Any]] = []
    scanned = 0
    skipped_non_ai = 0
    skipped_low_relevance = 0
    skipped_noise = 0
    missing_title = 0
    missing_summary = 0
    missing_url = 0
    for node in items[:per_source_limit * 2]:
        scanned += 1
        title = get_child_text(node, ["title", "{http://www.w3.org/2005/Atom}title"])
        summary = get_child_text(
            node,
            [
                "description",
                "summary",
                "content",
                "{http://www.w3.org/2005/Atom}summary",
                "{http://www.w3.org/2005/Atom}content",
            ],
        )
        link = get_link(node)
        published = get_child_text(
            node,
            [
                "pubDate",
                "published",
                "updated",
                "dc:date",
                "{http://www.w3.org/2005/Atom}published",
                "{http://www.w3.org/2005/Atom}updated",
            ],
        )

        cleaned_title = normalize_text(maybe_fix_mojibake(strip_html(title)))
        cleaned_summary = normalize_text(maybe_fix_mojibake(strip_html(summary)))
        text_blob = f"{cleaned_title} {cleaned_summary}".lower()
        relevance = ai_relevance_assessment(text_blob, source_always_ai=always_ai)
        if relevance["blocked_by_noise"]:
            skipped_noise += 1
            continue
        if not relevance["is_relevant"]:
            skipped_non_ai += 1
            continue
        if relevance["score"] < min_relevance_score:
            skipped_low_relevance += 1
            continue
        if not title:
            missing_title += 1
        if not summary:
            missing_summary += 1
        if not link:
            missing_url += 1

        results.append(
            {
                "title": cleaned_title,
                "summary": cleaned_summary,
                "source": source_name,
                "source_type": source_type,
                "source_weight": source_weight,
                "source_region": source_region,
                "url": link.strip(),
                "published_at": parse_date(published).isoformat(),
                "ai_relevance_score": relevance["score"],
                "ai_relevance_reason": relevance["reason"],
            }
        )
        if len(results) >= per_source_limit:
            break

    duration = time.perf_counter() - start
    LOGGER.info(
        "Fetched RSS done: source=%s scanned=%d kept=%d skipped_non_ai=%d skipped_low_relevance=%d skipped_noise=%d missing_title=%d missing_summary=%d missing_url=%d cost=%.2fs",
        source_name,
        scanned,
        len(results),
        skipped_non_ai,
        skipped_low_relevance,
        skipped_noise,
        missing_title,
        missing_summary,
        missing_url,
        duration,
    )
    return results


def load_fallback() -> list[dict[str, Any]]:
    if not FALLBACK_FILE.exists():
        LOGGER.warning("Fallback file not found: %s", FALLBACK_FILE)
        return []
    with FALLBACK_FILE.open("r", encoding="utf-8-sig") as f:
        payload = json.load(f)
    news = payload.get("news", [])
    LOGGER.info("Loaded fallback items: %d", len(news))
    return news


def ai_relevance_assessment(text: str, source_always_ai: bool = False) -> dict[str, Any]:
    normalized = normalize_text((text or "").lower())
    strong_hits = [kw for kw in AI_STRONG_KEYWORDS if kw in normalized]
    weak_hits = [kw for kw in AI_KEYWORDS if kw in normalized]
    noise_hits = [kw for kw in AI_NOISE_KEYWORDS if kw in normalized]
    campus_hits = [kw for kw in CAMPUS_CONTEXT_KEYWORDS if kw in normalized]
    tech_hits = [kw for kw in AI_TECH_SIGNAL_KEYWORDS if kw in normalized]
    campus_noise = len(campus_hits) >= 2 and len(tech_hits) == 0

    score = len(strong_hits) * 2 + len(set(weak_hits))
    if source_always_ai:
        score += 2
    if noise_hits and len(strong_hits) == 0:
        score -= 2
    if campus_noise:
        score = max(0, score - 3)

    score = max(0, min(10, score))
    is_relevant = source_always_ai or score >= 2
    blocked_by_noise = bool(noise_hits and len(strong_hits) == 0 and score < 3)
    if campus_noise and not source_always_ai:
        blocked_by_noise = True
    if blocked_by_noise:
        is_relevant = False

    reason_parts = []
    if strong_hits:
        reason_parts.append(f"strong={len(strong_hits)}")
    if weak_hits:
        reason_parts.append(f"weak={len(set(weak_hits))}")
    if noise_hits:
        reason_parts.append(f"noise={len(noise_hits)}")
    if campus_noise:
        reason_parts.append(f"campus_noise={len(campus_hits)}")
    if tech_hits:
        reason_parts.append(f"tech={len(tech_hits)}")
    if source_always_ai:
        reason_parts.append("always_ai_source")

    return {
        "score": score,
        "is_relevant": is_relevant,
        "blocked_by_noise": blocked_by_noise,
        "reason": ",".join(reason_parts) if reason_parts else "no_signal",
    }


def is_ai_related(text: str) -> bool:
    return ai_relevance_assessment(text)["is_relevant"]


def detect_language(text: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    if re.search(r"[A-Za-z]", text):
        return "en"
    return "other"


def make_id(url: str, title: str) -> str:
    digest = hashlib.sha256(f"{url}|{title}".encode("utf-8")).hexdigest()
    return digest[:16]


def canonical_title(title: str) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff]+", " ", title.lower())
    text = re.sub(r"\s+", " ", text).strip()
    return text


def deduplicate(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_url: set[str] = set()
    seen_title: set[str] = set()
    unique: list[dict[str, Any]] = []
    dup_url = 0
    dup_title = 0
    for item in items:
        url = item.get("url", "").strip()
        title_key = canonical_title(item.get("title", ""))
        if url and url in seen_url:
            dup_url += 1
            continue
        if title_key and title_key in seen_title:
            dup_title += 1
            continue

        seen_url.add(url)
        seen_title.add(title_key)
        unique.append(item)
    LOGGER.info(
        "Dedup summary: input=%d output=%d dup_url=%d dup_title=%d",
        len(items),
        len(unique),
        dup_url,
        dup_title,
    )
    return unique


def parse_iso_utc(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc) - timedelta(days=3650)


def balanced_select(items: list[dict[str, Any]], max_items: int, min_per_source: int) -> list[dict[str, Any]]:
    if not items:
        return []

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in items:
        grouped.setdefault(row.get("source", "unknown"), []).append(row)

    for source_rows in grouped.values():
        source_rows.sort(key=lambda x: parse_iso_utc(x.get("published_at", "")), reverse=True)

    picked: list[dict[str, Any]] = []
    picked_ids: set[str] = set()

    # First pass: keep minimal representation per source.
    for source_name in sorted(grouped.keys()):
        limit = min(min_per_source, len(grouped[source_name]))
        for row in grouped[source_name][:limit]:
            row_id = make_id(row.get("url", ""), row.get("title", ""))
            if row_id in picked_ids:
                continue
            picked.append(row)
            picked_ids.add(row_id)
            if len(picked) >= max_items:
                break
        if len(picked) >= max_items:
            break

    if len(picked) >= max_items:
        return picked[:max_items]

    # Second pass: fill remaining slots by recency across all leftovers.
    leftovers = sorted(items, key=lambda x: parse_iso_utc(x.get("published_at", "")), reverse=True)
    for row in leftovers:
        row_id = make_id(row.get("url", ""), row.get("title", ""))
        if row_id in picked_ids:
            continue
        picked.append(row)
        picked_ids.add(row_id)
        if len(picked) >= max_items:
            break

    return picked[:max_items]


def match_tags(text: str, rules: dict[str, list[str]]) -> list[str]:
    matched: list[str] = []
    low = text.lower()
    for tag, keywords in rules.items():
        if any(kw in low for kw in keywords):
            matched.append(tag)
    return matched


def infer_topic_tags_fallback(item: dict[str, Any], text: str, event_type: str) -> list[str]:
    inferred: list[str] = []
    source_type = item.get("source_type", "")
    lower = text.lower()

    if source_type == "research":
        inferred.append("Research")
    if source_type == "official":
        inferred.append("Model Release")
    if source_type == "social":
        inferred.append("Application")

    if event_type == "Funding":
        inferred.append("Capital")
    if event_type == "Policy":
        inferred.append("Policy")
    if event_type == "Incident":
        inferred.append("Safety")

    if "job" in lower or "就业" in lower or "workforce" in lower:
        inferred.append("Application")
    if "school" in lower or "education" in lower or "教育" in lower or "学院" in lower or "大学" in lower:
        inferred.append("Application")
    if "github" in lower or "registry" in lower or "sdk" in lower:
        inferred.append("Application")
    if "safety" in lower or "security" in lower:
        inferred.append("Safety")
    if (
        "united nations" in lower
        or "international cooperation" in lower
        or "联合国" in lower
        or "国际合作" in lower
        or "能力建设" in lower
    ):
        inferred.append("Policy")

    deduped: list[str] = []
    for tag in inferred:
        if tag not in deduped:
            deduped.append(tag)
    return deduped[:3]


def pick_event_type(text: str) -> str:
    low = text.lower()
    for event_type, keywords in EVENT_RULES.items():
        if any(kw in low for kw in keywords):
            return event_type
    return "General"


def guess_entities(text: str) -> list[str]:
    known_entities = [
        "OpenAI",
        "Anthropic",
        "Google",
        "Microsoft",
        "Meta",
        "NVIDIA",
        "DeepMind",
        "Tesla",
        "Amazon",
        "ByteDance",
        "百度",
        "阿里",
        "腾讯",
        "华为",
    ]
    hits = [name for name in known_entities if name.lower() in text.lower()]

    # Capture extra English entities from capitalized phrases
    extra = re.findall(r"\b([A-Z][a-zA-Z0-9]{2,}(?:\s+[A-Z][a-zA-Z0-9]{2,}){0,2})\b", text)
    for token in extra[:6]:
        if token not in hits and len(token) <= 40:
            hits.append(token)

    deduped: list[str] = []
    for name in hits:
        if name not in deduped:
            deduped.append(name)
    return deduped[:8]


def sentiment_of(text: str) -> str:
    low = text.lower()
    pos = sum(1 for k in SENTIMENT_POS if k in low)
    neg = sum(1 for k in SENTIMENT_NEG if k in low)
    if neg > pos:
        return "neg"
    if pos > neg:
        return "pos"
    return "neu"


def recency_score(published_at: str) -> float:
    now = datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(published_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        return 40.0
    delta = now - dt
    if delta <= timedelta(hours=24):
        return 100.0
    if delta <= timedelta(hours=72):
        return 80.0
    if delta <= timedelta(days=7):
        return 65.0
    if delta <= timedelta(days=30):
        return 50.0
    return 30.0


def calc_impact(item: dict[str, Any], tags: list[str], event_type: str, sentiment: str) -> float:
    base = 48.0
    base += recency_score(item["published_at"]) * 0.20
    source_weight = item.get("source_weight", SOURCE_WEIGHTS.get(item.get("source", ""), 0.7))
    base += source_weight * 20
    base += min(len(tags), 3) * 4

    if event_type in {"Release", "Policy", "Funding"}:
        base += 7
    if sentiment == "neg":
        base += 3

    return max(0.0, min(100.0, round(base, 2)))


def confidence_score(item: dict[str, Any], tags: list[str], entities: list[str], evidence: list[str]) -> float:
    score = 0.45
    if len(item.get("summary", "")) >= 80:
        score += 0.15
    if tags:
        score += 0.15
    if entities:
        score += 0.15
    if len(evidence) >= 2:
        score += 0.10
    return round(min(score, 0.98), 2)


def build_evidence(title: str, summary: str) -> list[str]:
    points = []
    if title:
        points.append(title)
    sentences = re.split(r"(?<=[.!?。；;])\s+", summary)
    for sent in sentences:
        s = sent.strip()
        if len(s) >= 25:
            points.append(s)
        if len(points) >= 3:
            break
    return points[:3]


def extract_structured(item: dict[str, Any]) -> dict[str, Any]:
    text = f"{item['title']} {item['summary']}"
    try:
        source_weight = float(item.get("source_weight", SOURCE_WEIGHTS.get(item.get("source", ""), 0.7)))
    except Exception:
        source_weight = SOURCE_WEIGHTS.get(item.get("source", ""), 0.7)
    topic_tags = match_tags(text, TOPIC_RULES)
    event_type = pick_event_type(text)
    if not topic_tags:
        topic_tags = infer_topic_tags_fallback(item, text, event_type)
    entities = guess_entities(text)
    sentiment = sentiment_of(text)
    risk_tags = match_tags(text, RISK_RULES)
    opportunity_tags = match_tags(text, OPPORTUNITY_RULES)
    evidence = build_evidence(item["title"], item["summary"])
    impact = calc_impact(item, topic_tags, event_type, sentiment)
    confidence = confidence_score(item, topic_tags, entities, evidence)

    return {
        "id": make_id(item.get("url", ""), item.get("title", "")),
        "title": item.get("title", ""),
        "source": item.get("source", ""),
        "source_type": item.get("source_type", "unknown"),
        "source_weight": round(source_weight, 3),
        "source_region": item.get("source_region", "global"),
        "url": item.get("url", ""),
        "published_at": item.get("published_at", ""),
        "language": detect_language(f"{item.get('title', '')} {item.get('summary', '')}"),
        "raw_summary": item.get("summary", ""),
        "ai_relevance_score": item.get("ai_relevance_score", 0),
        "ai_relevance_reason": item.get("ai_relevance_reason", ""),
        "topic_tags": topic_tags,
        "entities": entities,
        "event_type": event_type,
        "sentiment": sentiment,
        "impact_score": impact,
        "risk_tags": risk_tags,
        "opportunity_tags": opportunity_tags,
        "evidence": evidence,
        "extract_confidence": confidence,
    }


def parse_json_payload_from_text(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Empty model output")

    # Strip markdown fences if the model returns fenced JSON.
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Best effort: capture first JSON object block.
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw[start : end + 1])
        raise


def call_openai_extraction_batch(
    batch_rows: list[dict[str, Any]],
    llm_model: str,
    llm_timeout_sec: int,
    prompt_template: str,
) -> list[dict[str, Any]]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    # Constrain LLM output to semantic fields and keep deterministic pipeline fields local.
    requested_fields = [
        "topic_tags",
        "entities",
        "event_type",
        "sentiment",
        "risk_tags",
        "opportunity_tags",
        "evidence",
        "extract_confidence",
    ]
    batch_payload = []
    for idx, row in enumerate(batch_rows):
        batch_payload.append(
            {
                "index": idx,
                "title": row.get("title", ""),
                "summary": row.get("summary", ""),
                "source": row.get("source", ""),
                "published_at": row.get("published_at", ""),
                "language_hint": detect_language(f"{row.get('title', '')} {row.get('summary', '')}"),
            }
        )

    user_prompt = (
        f"{prompt_template}\n\n"
        "Return JSON only using this shape:\n"
        '{ "items": [ { "index": number, "topic_tags": [], "entities": [], "event_type": "", "sentiment": "", "risk_tags": [], "opportunity_tags": [], "evidence": [], "extract_confidence": 0.0 } ] }\n'
        f"Requested semantic fields: {', '.join(requested_fields)}\n"
        "Rules:\n"
        "1) items length must equal input length.\n"
        "2) index must map to input item.\n"
        "3) event_type in [Release, Partnership, Funding, Policy, Incident, Research, General].\n"
        "4) sentiment in [pos, neu, neg].\n"
        "5) extract_confidence between 0 and 1.\n"
        "6) topic_tags/risk_tags/opportunity_tags/entities/evidence are arrays.\n\n"
        f"Input items:\n{json.dumps(batch_payload, ensure_ascii=False)}"
    )

    request_payload = {
        "model": llm_model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "You extract structured AI-news semantics. Output valid JSON only.",
            },
            {"role": "user", "content": user_prompt},
        ],
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(request_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=max(10, llm_timeout_sec)) as resp:
        raw_resp = resp.read().decode("utf-8")

    parsed_resp = json.loads(raw_resp)
    choice = (parsed_resp.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content", "")
    parsed = parse_json_payload_from_text(content)
    items = parsed.get("items")
    if not isinstance(items, list):
        raise ValueError("LLM output missing items[]")
    return items


def apply_llm_semantic_overlay(rule_record: dict[str, Any], llm_item: dict[str, Any]) -> dict[str, Any]:
    merged = dict(rule_record)
    if not isinstance(llm_item, dict):
        return merged

    def as_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return []

    topic_tags = as_list(llm_item.get("topic_tags"))
    entities = as_list(llm_item.get("entities"))
    risk_tags = as_list(llm_item.get("risk_tags"))
    opp_tags = as_list(llm_item.get("opportunity_tags"))
    evidence = as_list(llm_item.get("evidence"))

    if topic_tags:
        merged["topic_tags"] = topic_tags[:8]
    if entities:
        merged["entities"] = entities[:10]
    if risk_tags:
        merged["risk_tags"] = risk_tags[:6]
    if opp_tags:
        merged["opportunity_tags"] = opp_tags[:6]
    if evidence:
        merged["evidence"] = evidence[:3]

    event_type = str(llm_item.get("event_type", "")).strip()
    if event_type in {"Release", "Partnership", "Funding", "Policy", "Incident", "Research", "General"}:
        merged["event_type"] = event_type

    sentiment = str(llm_item.get("sentiment", "")).strip()
    if sentiment in {"pos", "neu", "neg"}:
        merged["sentiment"] = sentiment

    try:
        conf = float(llm_item.get("extract_confidence", merged.get("extract_confidence", 0.6)))
        merged["extract_confidence"] = round(max(0.0, min(1.0, conf)), 2)
    except Exception:
        pass

    # Recalculate impact score after semantic overlay to keep ranking consistent.
    merged["impact_score"] = calc_impact(merged, merged["topic_tags"], merged["event_type"], merged["sentiment"])
    return merged


def extract_structured_batch(
    batch_rows: list[dict[str, Any]],
    extract_mode: str,
    llm_model: str,
    llm_timeout_sec: int,
    prompt_template: str,
) -> tuple[list[dict[str, Any]], str]:
    rule_records = [extract_structured(row) for row in batch_rows]
    mode = (extract_mode or "rule").lower()
    if mode == "rule":
        return rule_records, "rule"

    try:
        llm_items = call_openai_extraction_batch(
            batch_rows=batch_rows,
            llm_model=llm_model,
            llm_timeout_sec=llm_timeout_sec,
            prompt_template=prompt_template,
        )
        indexed_llm: dict[int, dict[str, Any]] = {}
        for i, item in enumerate(llm_items):
            if not isinstance(item, dict):
                continue
            idx = item.get("index")
            try:
                mapped = int(idx)
            except Exception:
                mapped = i
            if 0 <= mapped < len(rule_records):
                indexed_llm[mapped] = item

        merged: list[dict[str, Any]] = []
        for idx, rule_record in enumerate(rule_records):
            llm_item = indexed_llm.get(idx, {})
            merged.append(apply_llm_semantic_overlay(rule_record, llm_item))
        return merged, "llm"
    except Exception as exc:
        if mode == "llm":
            LOGGER.warning("LLM extraction failed; fallback to rule for this batch: %s", exc)
            return rule_records, "rule_fallback"
        if mode == "hybrid":
            LOGGER.warning("Hybrid LLM extraction failed; fallback to rule for this batch: %s", exc)
            return rule_records, "rule_fallback"
        return rule_records, "rule"


def missing_required_fields(record: dict[str, Any], required_fields: list[str]) -> list[str]:
    missing: list[str] = []
    for field in required_fields:
        if field not in record:
            missing.append(field)
    return missing


def hot_score(record: dict[str, Any]) -> float:
    src_weight = record.get("source_weight", SOURCE_WEIGHTS.get(record.get("source", ""), 0.7)) * 100
    recency = recency_score(record.get("published_at", ""))
    cluster_hint = min(len(record.get("topic_tags", [])), 3) * 20
    score = (
        0.35 * record.get("impact_score", 0)
        + 0.25 * src_weight
        + 0.20 * recency
        + 0.20 * cluster_hint
    )
    return round(score, 2)


def top_hot_events(data: list[dict[str, Any]], top_n: int = 5) -> list[dict[str, Any]]:
    enriched = []
    for row in data:
        row2 = dict(row)
        row2["hot_score"] = hot_score(row)
        enriched.append(row2)
    enriched.sort(key=lambda x: x["hot_score"], reverse=True)
    return enriched[:top_n]


def summarize_trends(data: list[dict[str, Any]]) -> dict[str, Any]:
    topic_counter = Counter()
    event_counter = Counter()
    sentiment_counter = Counter()
    risk_counter = Counter()

    for row in data:
        for t in row.get("topic_tags", []):
            topic_counter[t] += 1
        event_counter[row.get("event_type", "General")] += 1
        sentiment_counter[row.get("sentiment", "neu")] += 1
        for r in row.get("risk_tags", []):
            risk_counter[r] += 1

    return {
        "topic_counter": topic_counter,
        "event_counter": event_counter,
        "sentiment_counter": sentiment_counter,
        "risk_counter": risk_counter,
    }


def profile_dataset(raw_news: list[dict[str, Any]], structured: list[dict[str, Any]]) -> dict[str, Any]:
    source_counter = Counter(row.get("source", "unknown") for row in raw_news)
    source_type_counter = Counter(row.get("source_type", "unknown") for row in raw_news)
    language_counter = Counter(row.get("language", "unknown") for row in structured)
    confidence_values = [row.get("extract_confidence", 0.0) for row in structured]
    impact_values = [row.get("impact_score", 0.0) for row in structured]
    relevance_values = [row.get("ai_relevance_score", 0.0) for row in structured]

    avg_conf = round(sum(confidence_values) / max(len(confidence_values), 1), 3)
    avg_impact = round(sum(impact_values) / max(len(impact_values), 1), 2)
    avg_relevance = round(sum(relevance_values) / max(len(relevance_values), 1), 2)
    high_impact = sum(1 for score in impact_values if score >= 85)
    low_conf = sum(1 for score in confidence_values if score < 0.60)

    return {
        "source_distribution": dict(source_counter),
        "source_type_distribution": dict(source_type_counter),
        "language_distribution": dict(language_counter),
        "avg_confidence": avg_conf,
        "avg_impact_score": avg_impact,
        "avg_relevance_score": avg_relevance,
        "high_impact_count": high_impact,
        "low_confidence_count": low_conf,
    }


def event_background_text(event_type: str, topic_tags: list[str]) -> str:
    tags = ", ".join(topic_tags[:3]) if topic_tags else "通用AI动态"
    mapping = {
        "Release": f"该事件属于能力发布类动态，通常意味着 {tags} 方向进入新一轮迭代。",
        "Funding": f"该事件属于资本驱动类动态，反映 {tags} 方向资源加速聚集。",
        "Policy": f"该事件属于政策监管类动态，直接影响 {tags} 的合规路径与上线节奏。",
        "Partnership": f"该事件属于生态合作类动态，说明 {tags} 正在通过协同推进落地。",
        "Incident": f"该事件属于风险事件，暴露 {tags} 在稳定性或治理层面的潜在问题。",
        "Research": f"该事件属于研究进展，表明 {tags} 方向仍在提升技术上限。",
    }
    return mapping.get(event_type, f"该事件属于综合行业动态，与 {tags} 相关。")


def event_impact_text(sentiment: str, risk_tags: list[str], opportunity_tags: list[str]) -> str:
    sentiment_text = {"pos": "偏正向", "neu": "中性", "neg": "偏负向"}.get(sentiment, "中性")
    risk_text = "、".join(risk_tags[:2]) if risk_tags else "暂无突出风险标签"
    opp_text = "、".join(opportunity_tags[:2]) if opportunity_tags else "暂无显著机会标签"
    return f"舆情情绪{sentiment_text}；风险侧关注 {risk_text}；机会侧关注 {opp_text}。"


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    LOGGER.info("Wrote JSONL: %s rows=%d", path, len(rows))


def render_visualization(structured: list[dict[str, Any]], trends: dict[str, Any], path: Path) -> None:
    records_json = json.dumps(structured, ensure_ascii=False).replace("</", "<\\/")
    trend_payload = {
        "topic_counter": dict(trends["topic_counter"]),
        "event_counter": dict(trends["event_counter"]),
        "sentiment_counter": dict(trends["sentiment_counter"]),
        "risk_counter": dict(trends["risk_counter"]),
    }
    trends_json = json.dumps(trend_payload, ensure_ascii=False).replace("</", "<\\/")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Daily AI Insight Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #f5faf8;
      --surface: rgba(255, 255, 255, 0.82);
      --surface-strong: #ffffff;
      --ink: #0d2026;
      --muted: #4d6670;
      --line: #d6e2e5;
      --accent: #0f9d8a;
      --accent-2: #e58f2a;
      --danger: #e25555;
      --shadow: 0 18px 45px rgba(16, 50, 64, 0.12);
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Noto Sans SC", "Space Grotesk", sans-serif;
      background:
        radial-gradient(circle at 15% -10%, #c4f0e9 0%, transparent 36%),
        radial-gradient(circle at 86% -20%, #ffe3c1 0%, transparent 38%),
        linear-gradient(140deg, #f8fcfb 0%, #eef6f4 100%);
      min-height: 100vh;
    }}

    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image: linear-gradient(rgba(33, 94, 106, 0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(33, 94, 106, 0.05) 1px, transparent 1px);
      background-size: 24px 24px;
      mask-image: radial-gradient(circle at 60% 5%, rgba(0, 0, 0, 0.8), transparent 80%);
      z-index: 0;
    }}

    .app {{
      position: relative;
      z-index: 1;
      max-width: 1180px;
      margin: 28px auto 54px;
      padding: 0 18px;
      display: grid;
      gap: 16px;
    }}

    .panel {{
      background: var(--surface);
      border: 1px solid rgba(255, 255, 255, 0.72);
      border-radius: 20px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
    }}

    .hero {{
      padding: 24px;
      display: flex;
      flex-wrap: wrap;
      align-items: flex-end;
      justify-content: space-between;
      gap: 18px;
      overflow: hidden;
      position: relative;
    }}

    .hero::after {{
      content: "";
      position: absolute;
      width: 260px;
      height: 260px;
      right: -40px;
      top: -95px;
      border-radius: 999px;
      background: radial-gradient(circle, rgba(15, 157, 138, 0.35), transparent 70%);
      pointer-events: none;
    }}

    .hero h1 {{
      margin: 0;
      font-family: "Space Grotesk", sans-serif;
      font-size: clamp(1.8rem, 3vw, 2.5rem);
      line-height: 1.05;
      letter-spacing: -0.03em;
    }}

    .hero p {{
      margin: 8px 0 0;
      color: var(--muted);
      max-width: 64ch;
      line-height: 1.5;
    }}

    .hero-meta {{
      display: grid;
      gap: 8px;
      min-width: 248px;
    }}

    .tag {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      border: 1px solid #bfd4d8;
      background: #f5fffc;
      padding: 8px 12px;
      font-size: 0.84rem;
      color: #18414c;
      width: fit-content;
    }}

    .kpis {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }}

    .kpi {{
      padding: 14px 16px 16px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: var(--surface-strong);
    }}

    .kpi-label {{
      font-size: 0.78rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-family: "Space Grotesk", sans-serif;
    }}

    .kpi-value {{
      margin-top: 8px;
      font-family: "Space Grotesk", sans-serif;
      font-size: clamp(1.4rem, 2.6vw, 2rem);
      font-weight: 700;
      letter-spacing: -0.03em;
    }}

    .kpi-sub {{
      margin-top: 3px;
      color: var(--muted);
      font-size: 0.82rem;
    }}

    .controls {{
      padding: 14px 18px;
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
    }}

    .control-group {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }}

    .control-label {{
      font-size: 0.82rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-family: "Space Grotesk", sans-serif;
    }}

    select {{
      min-width: 172px;
      padding: 9px 11px;
      border-radius: 10px;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      font-size: 0.92rem;
    }}

    .chips {{
      display: inline-flex;
      gap: 8px;
      padding: 5px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #fff;
    }}

    .chip {{
      border: 0;
      background: transparent;
      padding: 7px 11px;
      border-radius: 999px;
      font-size: 0.84rem;
      color: #35545d;
      cursor: pointer;
      transition: background .22s ease, color .22s ease, transform .22s ease;
    }}

    .chip:hover {{
      transform: translateY(-1px);
      background: #edf5f5;
    }}

    .chip.active {{
      background: var(--accent);
      color: #fff;
      box-shadow: 0 8px 18px rgba(15, 157, 138, 0.25);
    }}

    .action-btn {{
      border: 0;
      border-radius: 10px;
      padding: 9px 12px;
      font-size: 0.84rem;
      font-family: "Space Grotesk", sans-serif;
      color: #fff;
      background: linear-gradient(120deg, #138f80, #0f6a8f);
      cursor: pointer;
      transition: transform .2s ease, box-shadow .2s ease;
      box-shadow: 0 10px 20px rgba(15, 106, 143, 0.25);
    }}

    .action-btn:hover {{
      transform: translateY(-1px);
    }}

    .layout {{
      display: grid;
      grid-template-columns: 1.25fr 0.95fr;
      gap: 14px;
    }}

    .panel-title {{
      margin: 0;
      font-size: 1rem;
      font-family: "Space Grotesk", sans-serif;
      letter-spacing: -0.01em;
    }}

    .chart-panel {{
      padding: 16px;
      min-height: 250px;
    }}

    .topic-bars {{
      margin-top: 14px;
      display: grid;
      gap: 9px;
    }}

    .topic-row {{
      display: grid;
      gap: 6px;
    }}

    .topic-head {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      font-size: 0.88rem;
      color: #29434c;
    }}

    .topic-track {{
      height: 10px;
      border-radius: 999px;
      background: #e7eff0;
      overflow: hidden;
    }}

    .topic-fill {{
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, #13a08d, #32c4ad);
      transform-origin: left center;
      animation: growBar .72s ease both;
    }}

    @keyframes growBar {{
      from {{ transform: scaleX(0.12); opacity: 0.2; }}
      to {{ transform: scaleX(1); opacity: 1; }}
    }}

    .sentiment-wrap {{
      margin-top: 14px;
      display: grid;
      grid-template-columns: 150px 1fr;
      gap: 12px;
      align-items: center;
    }}

    .donut {{
      width: 150px;
      height: 150px;
      border-radius: 999px;
      position: relative;
      box-shadow: inset 0 0 0 1px #d9e5e7;
    }}

    .donut::before {{
      content: "";
      position: absolute;
      inset: 26%;
      border-radius: 999px;
      background: #fff;
      box-shadow: inset 0 0 0 1px #dfe8ea;
    }}

    .donut-center {{
      position: absolute;
      inset: 0;
      display: grid;
      place-items: center;
      font-family: "Space Grotesk", sans-serif;
      font-weight: 700;
      font-size: 0.95rem;
      color: #27434d;
      z-index: 1;
      text-align: center;
      line-height: 1.05;
    }}

    .legend {{
      display: grid;
      gap: 8px;
    }}

    .legend-item {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 7px 10px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #fff;
      font-size: 0.86rem;
      color: #2d4b54;
    }}

    .legend-left {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }}

    .dot {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
    }}

    .timeline-wrap {{
      margin-top: 14px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: #fff;
      padding: 12px;
    }}

    .timeline-svg {{
      width: 100%;
      height: 172px;
      display: block;
    }}

    .timeline-axis {{
      margin-top: 8px;
      display: flex;
      justify-content: space-between;
      font-size: 0.78rem;
      color: #5b7076;
    }}

    .events {{
      padding: 16px;
    }}

    .events-head {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      margin-bottom: 10px;
    }}

    .events-list {{
      display: grid;
      gap: 10px;
      max-height: 540px;
      overflow: auto;
      padding-right: 4px;
    }}

    .event-card {{
      border: 1px solid var(--line);
      border-radius: 14px;
      background: #fff;
      padding: 12px;
      display: grid;
      gap: 8px;
      transition: transform .24s ease, box-shadow .24s ease;
    }}

    .event-card:hover {{
      transform: translateY(-2px);
      box-shadow: 0 12px 28px rgba(20, 52, 63, 0.12);
    }}

    .event-title {{
      font-size: 0.96rem;
      font-weight: 600;
      line-height: 1.35;
      color: #14313a;
      margin: 0;
    }}

    .event-meta {{
      color: #587179;
      font-size: 0.78rem;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}

    .pills {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }}

    .pill {{
      border-radius: 999px;
      background: #edf6f6;
      color: #22505d;
      font-size: 0.74rem;
      padding: 4px 8px;
      border: 1px solid #d8e8ea;
    }}

    .score {{
      display: inline-flex;
      gap: 6px;
      align-items: center;
      font-family: "Space Grotesk", sans-serif;
      font-size: 0.82rem;
      color: #16424d;
    }}

    .score strong {{
      font-size: 0.97rem;
    }}

    .empty {{
      border: 1px dashed var(--line);
      border-radius: 12px;
      color: #587179;
      padding: 16px;
      background: #fbfefe;
      font-size: 0.9rem;
    }}

    .footer-note {{
      color: #4f656d;
      font-size: 0.82rem;
      padding: 10px 4px 0;
      line-height: 1.5;
    }}

    @media (max-width: 980px) {{
      .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .layout {{ grid-template-columns: 1fr; }}
    }}

    @media (max-width: 640px) {{
      .app {{ margin-top: 14px; padding: 0 12px; }}
      .hero {{ padding: 18px; }}
      .controls {{ padding: 12px; }}
      .kpi-value {{ font-size: 1.45rem; }}
      .sentiment-wrap {{ grid-template-columns: 1fr; justify-items: center; }}
      .donut {{ width: 132px; height: 132px; }}
    }}
  </style>
</head>
<body>
  <main class="app">
    <section class="panel hero">
      <div>
        <h1>Daily AI Insight Dashboard</h1>
        <p>Interactive daily intelligence board for AI news. Filter by source and language, track momentum, and inspect high-impact events with evidence tags.</p>
      </div>
      <div class="hero-meta">
        <div class="tag">UTC Snapshot · <span id="snapshotTime">--</span></div>
        <div class="tag">Records in View · <span id="activeRecordCount">0</span></div>
      </div>
    </section>

    <section class="kpis" id="kpiBoard">
      <article class="panel kpi">
        <div class="kpi-label">Total News</div>
        <div class="kpi-value" data-kpi="total">0</div>
        <div class="kpi-sub">Filtered records</div>
      </article>
      <article class="panel kpi">
        <div class="kpi-label">Avg Impact</div>
        <div class="kpi-value" data-kpi="impact">0</div>
        <div class="kpi-sub">0 - 100 score</div>
      </article>
      <article class="panel kpi">
        <div class="kpi-label">Avg Confidence</div>
        <div class="kpi-value" data-kpi="confidence">0%</div>
        <div class="kpi-sub">Extraction quality</div>
      </article>
      <article class="panel kpi">
        <div class="kpi-label">Risk Tagged</div>
        <div class="kpi-value" data-kpi="risk">0</div>
        <div class="kpi-sub">Potential risk items</div>
      </article>
    </section>

    <section class="panel controls">
      <div class="control-group">
        <span class="control-label">Source</span>
        <select id="sourceFilter"></select>
      </div>
      <div class="control-group">
        <span class="control-label">Language</span>
        <div class="chips">
          <button class="chip" data-lang="all">All</button>
          <button class="chip active" data-lang="en">EN</button>
          <button class="chip" data-lang="zh">ZH</button>
        </div>
      </div>
      <div class="control-group">
        <span class="control-label">Sort</span>
        <select id="sortMode">
          <option value="hot">Hot Score</option>
          <option value="impact">Impact Score</option>
          <option value="newest">Newest First</option>
          <option value="confidence">Confidence</option>
        </select>
      </div>
      <div class="control-group">
        <button id="exportCsvBtn" class="action-btn" type="button">Export Filtered CSV</button>
      </div>
    </section>

    <section class="layout">
      <section class="panel chart-panel">
        <h3 class="panel-title">Topic Momentum</h3>
        <div id="topicBars" class="topic-bars"></div>
      </section>
      <section class="panel chart-panel">
        <h3 class="panel-title">Sentiment Mix</h3>
        <div class="sentiment-wrap">
          <div class="donut" id="sentimentDonut">
            <div class="donut-center"><span id="donutTotal">0</span><br>items</div>
          </div>
          <div id="sentimentLegend" class="legend"></div>
        </div>
      </section>
    </section>

    <section class="panel chart-panel">
      <h3 class="panel-title">Publish Timeline (UTC)</h3>
      <div class="timeline-wrap">
        <svg class="timeline-svg" id="timelineSvg" viewBox="0 0 740 170" preserveAspectRatio="none"></svg>
        <div id="timelineAxis" class="timeline-axis"></div>
      </div>
    </section>

    <section class="panel events">
      <div class="events-head">
        <h3 class="panel-title">Key Events</h3>
        <div class="tag">Sorted by <span id="sortLabel">Hot Score</span></div>
      </div>
      <div id="eventsList" class="events-list"></div>
    </section>

    <p class="footer-note">
      This dashboard is generated automatically from the daily pipeline output.
      Scores are heuristic and should be read with evidence context.
    </p>
  </main>

  <script>
    const RAW_RECORDS = {records_json};
    const TREND_META = {trends_json};
    const state = {{
      source: "all",
      language: "en",
      sortMode: "hot"
    }};

    const sortLabelMap = {{
      hot: "Hot Score",
      impact: "Impact Score",
      newest: "Newest First",
      confidence: "Confidence"
    }};

    function recencyScore(isoTime) {{
      const now = Date.now();
      const ts = Date.parse(isoTime);
      if (Number.isNaN(ts)) return 40;
      const deltaHours = (now - ts) / 3600000;
      if (deltaHours <= 24) return 100;
      if (deltaHours <= 72) return 80;
      if (deltaHours <= 24 * 7) return 65;
      if (deltaHours <= 24 * 30) return 50;
      return 30;
    }}

    function hotScore(row) {{
      const impact = Number(row.impact_score || 0);
      const src = Number(row.source_weight || 0.7) * 100;
      const rec = recencyScore(row.published_at);
      const topicCount = Math.min((row.topic_tags || []).length, 3) * 20;
      return Number((0.35 * impact + 0.25 * src + 0.20 * rec + 0.20 * topicCount).toFixed(2));
    }}

    function buildFilters() {{
      const sourceFilter = document.getElementById("sourceFilter");
      const uniqueSources = Array.from(new Set(RAW_RECORDS.map((r) => r.source))).sort();
      sourceFilter.innerHTML = ['<option value="all">All Sources</option>', ...uniqueSources.map((s) => `<option value="${{escapeHtml(s)}}">${{escapeHtml(s)}}</option>`)].join("");
      sourceFilter.addEventListener("change", (e) => {{
        state.source = e.target.value;
        updateDashboard();
      }});

      const chips = Array.from(document.querySelectorAll(".chip"));
      chips.forEach((chip) => {{
        chip.addEventListener("click", () => {{
          chips.forEach((c) => c.classList.remove("active"));
          chip.classList.add("active");
          state.language = chip.dataset.lang;
          updateDashboard();
        }});
      }});

      const sortMode = document.getElementById("sortMode");
      sortMode.addEventListener("change", (e) => {{
        state.sortMode = e.target.value;
        updateDashboard();
      }});

      const exportCsvBtn = document.getElementById("exportCsvBtn");
      exportCsvBtn.addEventListener("click", () => {{
        const filtered = filterRecords();
        const sorted = sortedRecords(filtered);
        exportFilteredCSV(sorted);
      }});
    }}

    function filterRecords() {{
      return RAW_RECORDS.filter((row) => {{
        const sourceOk = state.source === "all" || row.source === state.source;
        const languageOk = state.language === "all" || row.language === state.language;
        return sourceOk && languageOk;
      }});
    }}

    function sortedRecords(rows) {{
      const cloned = [...rows];
      if (state.sortMode === "newest") {{
        cloned.sort((a, b) => Date.parse(b.published_at || 0) - Date.parse(a.published_at || 0));
      }} else if (state.sortMode === "impact") {{
        cloned.sort((a, b) => (b.impact_score || 0) - (a.impact_score || 0));
      }} else if (state.sortMode === "confidence") {{
        cloned.sort((a, b) => (b.extract_confidence || 0) - (a.extract_confidence || 0));
      }} else {{
        cloned.sort((a, b) => hotScore(b) - hotScore(a));
      }}
      return cloned;
    }}

    function aggregateTopics(rows) {{
      const counter = new Map();
      rows.forEach((row) => {{
        const tags = (row.topic_tags || []).length ? row.topic_tags : ["General"];
        tags.forEach((tag) => counter.set(tag, (counter.get(tag) || 0) + 1));
      }});
      return Array.from(counter.entries()).sort((a, b) => b[1] - a[1]).slice(0, 8);
    }}

    function aggregateSentiment(rows) {{
      const counts = {{ pos: 0, neu: 0, neg: 0 }};
      rows.forEach((row) => {{
        const key = row.sentiment || "neu";
        if (counts[key] === undefined) counts[key] = 0;
        counts[key] += 1;
      }});
      return counts;
    }}

    function aggregateTimeline(rows) {{
      const counter = new Map();
      rows.forEach((row) => {{
        const d = Date.parse(row.published_at || "");
        if (Number.isNaN(d)) return;
        const key = new Date(d).toISOString().slice(0, 10);
        counter.set(key, (counter.get(key) || 0) + 1);
      }});
      return Array.from(counter.entries()).sort((a, b) => a[0].localeCompare(b[0]));
    }}

    function stats(rows) {{
      const total = rows.length;
      const avgImpact = total ? rows.reduce((acc, r) => acc + (r.impact_score || 0), 0) / total : 0;
      const avgConf = total ? rows.reduce((acc, r) => acc + (r.extract_confidence || 0), 0) / total : 0;
      const riskCount = rows.filter((r) => (r.risk_tags || []).length > 0).length;
      return {{
        total,
        avgImpact: Number(avgImpact.toFixed(1)),
        avgConf: Number((avgConf * 100).toFixed(1)),
        riskCount
      }};
    }}

    function animateValue(el, target, suffix = "") {{
      const previous = Number((el.dataset.value || "0").replace("%", ""));
      const delta = target - previous;
      const duration = 420;
      const start = performance.now();
      el.dataset.value = String(target);

      function step(now) {{
        const progress = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = previous + delta * eased;
        el.textContent = `${{current.toFixed(suffix ? 1 : 0)}}${{suffix}}`;
        if (progress < 1) requestAnimationFrame(step);
      }}
      requestAnimationFrame(step);
    }}

    function renderKpis(currentStats) {{
      animateValue(document.querySelector('[data-kpi="total"]'), currentStats.total);
      animateValue(document.querySelector('[data-kpi="impact"]'), currentStats.avgImpact);
      animateValue(document.querySelector('[data-kpi="confidence"]'), currentStats.avgConf, "%");
      animateValue(document.querySelector('[data-kpi="risk"]'), currentStats.riskCount);
      document.getElementById("activeRecordCount").textContent = String(currentStats.total);
    }}

    function renderTopics(topicEntries) {{
      const target = document.getElementById("topicBars");
      if (!topicEntries.length) {{
        target.innerHTML = '<div class="empty">No topic data under current filter.</div>';
        return;
      }}
      const max = Math.max(...topicEntries.map(([, count]) => count), 1);
      target.innerHTML = topicEntries.map(([tag, count]) => {{
        const width = Math.round((count / max) * 100);
        return `
          <div class="topic-row">
            <div class="topic-head"><span>${{escapeHtml(tag)}}</span><strong>${{count}}</strong></div>
            <div class="topic-track"><div class="topic-fill" style="width:${{width}}%"></div></div>
          </div>
        `;
      }}).join("");
    }}

    function renderSentiment(counts) {{
      const total = Object.values(counts).reduce((acc, n) => acc + n, 0) || 1;
      const pos = counts.pos || 0;
      const neu = counts.neu || 0;
      const neg = counts.neg || 0;
      const posDeg = (pos / total) * 360;
      const neuDeg = (neu / total) * 360;
      const negDeg = 360 - posDeg - neuDeg;

      const donut = document.getElementById("sentimentDonut");
      donut.style.background = `conic-gradient(#16a085 0deg ${{posDeg}}deg, #2e7dbe ${{posDeg}}deg ${{(posDeg + neuDeg).toFixed(2)}}deg, #e25555 ${{(posDeg + neuDeg).toFixed(2)}}deg 360deg)`;
      document.getElementById("donutTotal").textContent = String(total);

      const legend = document.getElementById("sentimentLegend");
      const rows = [
        {{ key: "Positive", color: "#16a085", value: pos }},
        {{ key: "Neutral", color: "#2e7dbe", value: neu }},
        {{ key: "Negative", color: "#e25555", value: neg }}
      ];
      legend.innerHTML = rows.map((row) => {{
        const pct = ((row.value / total) * 100).toFixed(1);
        return `
          <div class="legend-item">
            <span class="legend-left"><span class="dot" style="background:${{row.color}}"></span>${{row.key}}</span>
            <strong>${{row.value}} · ${{pct}}%</strong>
          </div>
        `;
      }}).join("");
    }}

    function renderTimeline(points) {{
      const svg = document.getElementById("timelineSvg");
      const axis = document.getElementById("timelineAxis");
      if (!points.length) {{
        svg.innerHTML = "";
        axis.innerHTML = "<span>No timeline data</span>";
        return;
      }}

      const width = 740;
      const height = 170;
      const padding = 16;
      const maxY = Math.max(...points.map(([, value]) => value), 1);
      const span = Math.max(points.length - 1, 1);
      const coords = points.map(([date, value], idx) => {{
        const x = padding + ((width - 2 * padding) * idx) / span;
        const y = height - padding - ((height - 2 * padding) * value) / maxY;
        return {{ date, value, x: Number(x.toFixed(2)), y: Number(y.toFixed(2)) }};
      }});

      const linePath = coords.map((p, i) => `${{i === 0 ? "M" : "L"}}${{p.x}},${{p.y}}`).join(" ");
      const areaPath = `${{linePath}} L${{coords[coords.length - 1].x}},${{height - padding}} L${{coords[0].x}},${{height - padding}} Z`;

      svg.innerHTML = `
        <defs>
          <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="rgba(19,160,141,0.42)"/>
            <stop offset="100%" stop-color="rgba(19,160,141,0.03)"/>
          </linearGradient>
        </defs>
        <path d="${{areaPath}}" fill="url(#areaGrad)"></path>
        <path d="${{linePath}}" fill="none" stroke="#118f7f" stroke-width="3" stroke-linecap="round"></path>
        ${{coords.map((p) => `<circle cx="${{p.x}}" cy="${{p.y}}" r="4.6" fill="#fff" stroke="#118f7f" stroke-width="2"><title>${{p.date}} · ${{p.value}}</title></circle>`).join("")}}
      `;

      const first = points[0][0];
      const last = points[points.length - 1][0];
      axis.innerHTML = `<span>${{first}}</span><span>${{last}}</span>`;
    }}

    function sentimentBadge(sentiment) {{
      if (sentiment === "pos") return "Positive";
      if (sentiment === "neg") return "Negative";
      return "Neutral";
    }}

    function renderEvents(rows) {{
      const container = document.getElementById("eventsList");
      if (!rows.length) {{
        container.innerHTML = '<div class="empty">No records match the current filters.</div>';
        return;
      }}

      container.innerHTML = rows.slice(0, 10).map((row) => {{
        const evidence = (row.evidence || []).slice(0, 1).map((line) => `<div class="pill">${{escapeHtml(line.slice(0, 120))}}</div>`).join("");
        const topicPills = (row.topic_tags || []).slice(0, 3).map((tag) => `<span class="pill">${{escapeHtml(tag)}}</span>`).join("") || '<span class="pill">General</span>';
        const score = hotScore(row);
        return `
          <article class="event-card">
            <h4 class="event-title">${{escapeHtml(row.title || "Untitled")}}</h4>
            <div class="event-meta">
              <span>${{escapeHtml(row.source || "Unknown Source")}}</span>
              <span>•</span>
              <span>${{escapeHtml(row.source_type || "unknown")}}</span>
              <span>•</span>
              <span>${{escapeHtml((row.published_at || "").replace("T", " ").replace("+00:00", " UTC"))}}</span>
              <span>•</span>
              <span>${{sentimentBadge(row.sentiment)}}</span>
            </div>
            <div class="pills">${{topicPills}}</div>
            <div class="score">Hot <strong>${{score}}</strong> · Impact <strong>${{Number(row.impact_score || 0).toFixed(1)}}</strong> · Confidence <strong>${{Math.round((row.extract_confidence || 0) * 100)}}%</strong> · Relevance <strong>${{Number(row.ai_relevance_score || 0).toFixed(1)}}</strong></div>
            <div class="pills">${{evidence}}</div>
          </article>
        `;
      }}).join("");
    }}

    function csvEscape(value) {{
      const text = String(value ?? "");
      if (text.includes(",") || text.includes("\"") || text.includes("\\n")) {{
        return `"${{text.replace(/"/g, '""')}}"`;
      }}
      return text;
    }}

    function exportFilteredCSV(rows) {{
      const headers = [
        "title",
        "source",
        "source_type",
        "published_at",
        "language",
        "event_type",
        "sentiment",
        "impact_score",
        "hot_score",
        "ai_relevance_score",
        "extract_confidence",
        "topic_tags",
        "risk_tags",
        "opportunity_tags",
        "url"
      ];

      const lines = [headers.join(",")];
      rows.forEach((row) => {{
        const hot = hotScore(row);
        const values = [
          row.title || "",
          row.source || "",
          row.source_type || "",
          row.published_at || "",
          row.language || "",
          row.event_type || "",
          row.sentiment || "",
          Number(row.impact_score || 0).toFixed(1),
          hot,
          Number(row.ai_relevance_score || 0).toFixed(1),
          Number(row.extract_confidence || 0).toFixed(2),
          (row.topic_tags || []).join("|"),
          (row.risk_tags || []).join("|"),
          (row.opportunity_tags || []).join("|"),
          row.url || ""
        ];
        lines.push(values.map(csvEscape).join(","));
      }});

      const csvContent = lines.join("\\n");
      const blob = new Blob([csvContent], {{ type: "text/csv;charset=utf-8;" }});
      const url = URL.createObjectURL(blob);
      const now = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
      const filename = `daily-ai-insight-${{now}}.csv`;
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }}

    function escapeHtml(value) {{
      return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }}

    function updateDashboard() {{
      const filtered = filterRecords();
      const sorted = sortedRecords(filtered);

      renderKpis(stats(filtered));
      renderTopics(aggregateTopics(filtered));
      renderSentiment(aggregateSentiment(filtered));
      renderTimeline(aggregateTimeline(filtered));
      renderEvents(sorted);

      document.getElementById("sortLabel").textContent = sortLabelMap[state.sortMode];
    }}

    function initSnapshot() {{
      const latest = RAW_RECORDS
        .map((r) => Date.parse(r.published_at || ""))
        .filter((v) => !Number.isNaN(v))
        .sort((a, b) => b - a)[0];
      if (!latest) {{
        document.getElementById("snapshotTime").textContent = "N/A";
        return;
      }}
      document.getElementById("snapshotTime").textContent = new Date(latest).toISOString().replace("T", " ").slice(0, 16);
    }}

    buildFilters();
    initSnapshot();
    updateDashboard();
  </script>
</body>
</html>"""

    path.write_text(html_content, encoding="utf-8")
    LOGGER.info("Rendered visualization: %s", path)


def render_report(
    structured: list[dict[str, Any]],
    hot_events: list[dict[str, Any]],
    trends: dict[str, Any],
    dataset_profile: dict[str, Any],
    schema_version: str,
    path: Path,
) -> None:
    topic_lines = [f"- {k}: {v}" for k, v in trends["topic_counter"].most_common(6)]
    event_lines = [f"- {k}: {v}" for k, v in trends["event_counter"].most_common(6)]
    source_lines = [f"- {k}: {v}" for k, v in dataset_profile["source_distribution"].items()]
    source_type_lines = [f"- {k}: {v}" for k, v in dataset_profile.get("source_type_distribution", {}).items()]
    lang_lines = [f"- {k}: {v}" for k, v in dataset_profile["language_distribution"].items()]

    hot_lines = []
    for idx, row in enumerate(hot_events, start=1):
        background = event_background_text(row["event_type"], row["topic_tags"])
        impact = event_impact_text(row["sentiment"], row["risk_tags"], row["opportunity_tags"])
        evidence_lines = "".join([f"     - 证据: {e}\n" for e in row.get("evidence", [])[:2]])
        hot_lines.append(
            f"{idx}. **{row['title']}**  \n"
            f"   - 来源: {row['source']} ({row.get('source_type', 'unknown')}) | 时间: {row['published_at']}  \n"
            f"   - 类型: {row['event_type']} | 主题: {', '.join(row['topic_tags']) or 'General'}  \n"
            f"   - 影响分: {row['impact_score']} | 热度分: {row['hot_score']} | 相关性分: {row.get('ai_relevance_score', 0)}  \n"
            f"   - 背景分析: {background}  \n"
            f"   - 影响分析: {impact}\n"
            f"{evidence_lines.rstrip()}"
        )

    risk_top = trends["risk_counter"].most_common(3)
    risk_lines = [f"- {k}: {v}" for k, v in risk_top] or ["- 暂未识别显著风险标签"]

    report = f"""# AI舆情分析日报

- 生成时间(UTC): {datetime.now(timezone.utc).isoformat()}
- 样本数量: {len(structured)}
- Schema版本: {schema_version}
- 数据文件: `data/raw/raw_news.jsonl`, `data/processed/structured_news.jsonl`

## 1) 今日主要热点 (Top {len(hot_events)})

{chr(10).join(hot_lines) if hot_lines else '暂无热点数据'}

## 2) 趋势判断

### 数据质量快照
- 平均抽取置信度: {dataset_profile['avg_confidence']}
- 平均影响分: {dataset_profile['avg_impact_score']}
- 平均AI相关性分: {dataset_profile.get('avg_relevance_score', 0)}
- 高影响事件数量(>=85): {dataset_profile['high_impact_count']}
- 低置信度事件数量(<0.60): {dataset_profile['low_confidence_count']}

### 来源分布
{chr(10).join(source_lines) if source_lines else '- 暂无数据'}

### 来源类型分布
{chr(10).join(source_type_lines) if source_type_lines else '- 暂无数据'}

### 语种分布
{chr(10).join(lang_lines) if lang_lines else '- 暂无数据'}

### 主题分布
{chr(10).join(topic_lines) if topic_lines else '- 暂无数据'}

### 事件类型分布
{chr(10).join(event_lines) if event_lines else '- 暂无数据'}

### 趋势解读
- 技术方向: 模型发布与研究动态仍是主线，说明基础能力迭代持续进行。 
- 应用方向: 企业应用/开发者工具相关标签出现，表明从模型竞争转向落地效率竞争。 
- 政策方向: 若政策标签频次上升，意味着合规与治理将影响产品上线节奏。 
- 资本方向: 融资/并购事件可作为景气度信号，需结合连续多日数据验证。 

## 3) 风险与机会提示

### 风险提示
{chr(10).join(risk_lines)}

### 机会提示
- 企业提效与自动化场景具备短期落地机会。
- 开发者工具链（API/Agent/SDK）仍是高频需求方向。
- 算力与推理优化相关事件可作为基础设施投资线索。

## 4) 可视化

- 可视化页面: `outputs/visualization.html`
- 运行日志: `outputs/pipeline.log`
"""
    path.write_text(report, encoding="utf-8")
    LOGGER.info("Rendered report: %s", path)


def render_report_json(
    structured: list[dict[str, Any]],
    hot_events: list[dict[str, Any]],
    trends: dict[str, Any],
    dataset_profile: dict[str, Any],
    schema_version: str,
    path: Path,
) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": schema_version,
        "sample_count": len(structured),
        "dataset_profile": dataset_profile,
        "top_events": hot_events,
        "trend_summary": {
            "topics": dict(trends["topic_counter"]),
            "event_types": dict(trends["event_counter"]),
            "sentiments": dict(trends["sentiment_counter"]),
            "risks": dict(trends["risk_counter"]),
            "source_types": dataset_profile.get("source_type_distribution", {}),
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    LOGGER.info("Rendered machine-readable report: %s", path)


def collect_news(
    max_items: int,
    per_source_limit: int,
    min_relevance_score: int,
    min_per_source: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    sources = load_sources()
    collected: list[dict[str, Any]] = []
    logs: list[str] = []

    LOGGER.info(
        "Collection start: source_count=%d per_source_limit=%d target_max=%d min_relevance=%d min_per_source=%d",
        len(sources),
        per_source_limit,
        max_items,
        min_relevance_score,
        min_per_source,
    )
    for src in sources:
        source_name = src["name"]
        try:
            items = fetch_rss(src, per_source_limit=per_source_limit, min_relevance_score=min_relevance_score)
            collected.extend(items)
            logs.append(f"[OK] {source_name}: {len(items)}")
            LOGGER.info("Source collected: %s items=%d total_so_far=%d", source_name, len(items), len(collected))
        except Exception as exc:
            logs.append(f"[WARN] {source_name}: {exc}")
            LOGGER.exception("Source failed: %s url=%s error=%s", source_name, src.get("url", ""), exc)

    if len(collected) < max_items:
        fallback = load_fallback()
        logs.append(f"[FALLBACK] loaded {len(fallback)} synthetic items")
        LOGGER.warning(
            "Primary collection below target (%d < %d), fallback enabled count=%d",
            len(collected),
            max_items,
            len(fallback),
        )
        for row in fallback:
            text_blob = f"{row.get('title', '')} {row.get('summary', '')}"
            relevance = ai_relevance_assessment(text_blob, source_always_ai=True)
            if relevance["score"] < min_relevance_score:
                continue
            row_copy = dict(row)
            row_copy["title"] = normalize_text(maybe_fix_mojibake(row_copy.get("title", "")))
            row_copy["summary"] = normalize_text(maybe_fix_mojibake(row_copy.get("summary", "")))
            row_copy.setdefault("source", "Fallback Synthetic")
            row_copy.setdefault("source_type", "fallback")
            row_copy.setdefault("source_region", "global")
            row_copy.setdefault("source_weight", SOURCE_TYPE_DEFAULT_WEIGHT["fallback"])
            row_copy["ai_relevance_score"] = relevance["score"]
            row_copy["ai_relevance_reason"] = relevance["reason"]
            collected.append(row_copy)
        LOGGER.info("After fallback, collected=%d", len(collected))
    else:
        LOGGER.info("Primary collection reached target without fallback: %d", len(collected))

    collected = deduplicate(collected)
    selected = balanced_select(collected, max_items=max_items, min_per_source=min_per_source)
    selected.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    LOGGER.info(
        "Collection completed: unique_count=%d final_count=%d min_per_source=%d",
        len(collected),
        len(selected),
        min_per_source,
    )
    return selected, logs


def run(
    max_items: int,
    per_source_limit: int,
    min_required: int,
    min_relevance_score: int = 2,
    min_per_source: int = 2,
    extract_batch_size: int = 5,
    extract_mode: str = "hybrid",
    llm_model: str = DEFAULT_LLM_MODEL,
    llm_timeout_sec: int = 45,
    log_level: str = "INFO",
) -> dict[str, Any]:
    ensure_dirs()
    setup_logger(log_level=log_level)
    run_start = time.perf_counter()
    schema = load_schema()
    schema_version = schema.get("version", "unknown")
    required_fields = schema.get("required", [])
    LOGGER.info(
        "Pipeline started: max_items=%d per_source_limit=%d min_required=%d min_relevance=%d min_per_source=%d extract_mode=%s llm_model=%s log_level=%s",
        max_items,
        per_source_limit,
        min_required,
        min_relevance_score,
        min_per_source,
        extract_mode,
        llm_model,
        log_level.upper(),
    )

    raw_news, logs = collect_news(
        max_items=max_items,
        per_source_limit=per_source_limit,
        min_relevance_score=min_relevance_score,
        min_per_source=min_per_source,
    )
    if len(raw_news) < min_required:
        LOGGER.error("Collection insufficient: got=%d required=%d", len(raw_news), min_required)
        raise RuntimeError(
            f"Insufficient news after collection: {len(raw_news)} < min_required={min_required}. "
            f"Please adjust sources or fallback data."
        )

    structured: list[dict[str, Any]] = []
    low_confidence = 0
    no_topic = 0
    schema_error_count = 0
    effective_batch_size = max(1, extract_batch_size)
    prompt_template = load_extract_prompt()
    llm_batches = 0
    rule_batches = 0
    LOGGER.info("Structured extraction uses batching: batch_size=%d", effective_batch_size)
    processed_count = 0
    for batch_start in range(0, len(raw_news), effective_batch_size):
        batch_rows = raw_news[batch_start : batch_start + effective_batch_size]
        batch_index = batch_start // effective_batch_size + 1
        LOGGER.info("Structured extraction batch start: index=%d size=%d", batch_index, len(batch_rows))
        batch_structured, extractor_used = extract_structured_batch(
            batch_rows=batch_rows,
            extract_mode=extract_mode,
            llm_model=llm_model,
            llm_timeout_sec=llm_timeout_sec,
            prompt_template=prompt_template,
        )
        if extractor_used == "llm":
            llm_batches += 1
        else:
            rule_batches += 1

        for extracted in batch_structured:
            missing_fields = missing_required_fields(extracted, required_fields)
            if missing_fields:
                schema_error_count += 1
                LOGGER.warning("Schema mismatch on id=%s missing=%s", extracted.get("id", "n/a"), ",".join(missing_fields))
            structured.append(extracted)
            if extracted["extract_confidence"] < 0.60:
                low_confidence += 1
            if not extracted["topic_tags"]:
                no_topic += 1
            processed_count += 1
        LOGGER.info("Structured extraction batch done: index=%d progress=%d/%d", batch_index, processed_count, len(raw_news))
    LOGGER.info("Extraction engine usage: llm_batches=%d rule_batches=%d", llm_batches, rule_batches)
    LOGGER.info(
        "Structured extraction summary: total=%d low_confidence=%d no_topic=%d",
        len(structured),
        low_confidence,
        no_topic,
    )
    if low_confidence > 0:
        LOGGER.warning("There are %d low-confidence records for manual review", low_confidence)
    if no_topic > 0:
        LOGGER.warning("There are %d records without topic tags; consider refining rules", no_topic)
    if schema_error_count > 0:
        LOGGER.warning("There are %d records failing schema required-field checks", schema_error_count)

    hot_events = top_hot_events(structured, top_n=min(5, len(structured)))
    trends = summarize_trends(structured)
    dataset_profile = profile_dataset(raw_news, structured)
    LOGGER.info(
        "Analysis summary: hot=%d topic_types=%d risk_types=%d",
        len(hot_events),
        len(trends["topic_counter"]),
        len(trends["risk_counter"]),
    )

    raw_path = RAW_DIR / "raw_news.jsonl"
    structured_path = PROCESSED_DIR / "structured_news.jsonl"
    report_path = OUTPUT_DIR / "daily_report.md"
    report_json_path = OUTPUT_DIR / "daily_report.json"
    visual_path = OUTPUT_DIR / "visualization.html"

    write_jsonl(raw_path, raw_news)
    write_jsonl(structured_path, structured)
    render_visualization(structured, trends, visual_path)
    render_report(structured, hot_events, trends, dataset_profile, schema_version, report_path)
    render_report_json(structured, hot_events, trends, dataset_profile, schema_version, report_json_path)

    run_log = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": schema_version,
        "run_params": {
            "max_items": max_items,
            "per_source_limit": per_source_limit,
            "min_required": min_required,
            "min_relevance_score": min_relevance_score,
            "min_per_source": min_per_source,
            "extract_batch_size": effective_batch_size,
            "extract_mode": extract_mode,
            "llm_model": llm_model,
            "llm_timeout_sec": llm_timeout_sec,
        },
        "counts": {
            "raw": len(raw_news),
            "structured": len(structured),
            "hot": len(hot_events),
        },
        "artifacts": {
            "raw": str(raw_path),
            "structured": str(structured_path),
            "report": str(report_path),
            "report_json": str(report_json_path),
            "visual": str(visual_path),
            "pipeline_log": str(LOG_FILE),
        },
        "collector_logs": logs,
        "quality": {
            "low_confidence": low_confidence,
            "no_topic": no_topic,
            "schema_error_count": schema_error_count,
            "source_diversity_count": len(dataset_profile.get("source_distribution", {})),
            "llm_batches": llm_batches,
            "rule_batches": rule_batches,
        },
        "dataset_profile": dataset_profile,
    }

    (OUTPUT_DIR / "run_log.json").write_text(json.dumps(run_log, ensure_ascii=False, indent=2), encoding="utf-8")
    elapsed = time.perf_counter() - run_start
    LOGGER.info("Run log saved: %s", OUTPUT_DIR / "run_log.json")
    LOGGER.info("Pipeline finished successfully in %.2fs", elapsed)
    return run_log


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily AI Insight Engine MVP")
    parser.add_argument("--max-items", type=int, default=20, help="Maximum news items in final dataset")
    parser.add_argument("--per-source-limit", type=int, default=8, help="Per source fetch cap")
    parser.add_argument("--min-required", type=int, default=10, help="Minimum items required to continue")
    parser.add_argument("--min-relevance-score", type=int, default=2, help="Minimum AI relevance score (0-10)")
    parser.add_argument("--min-per-source", type=int, default=2, help="Diversity quota per source before global fill")
    parser.add_argument("--extract-batch-size", type=int, default=5, help="Structured extraction batch size")
    parser.add_argument("--extract-mode", type=str, default="hybrid", choices=["rule", "hybrid", "llm"], help="Extraction engine mode")
    parser.add_argument("--llm-model", type=str, default=DEFAULT_LLM_MODEL, help="LLM model for online extraction")
    parser.add_argument("--llm-timeout-sec", type=int, default=45, help="Timeout seconds per LLM batch request")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Log verbosity")
    return parser.parse_args()


def main() -> None:
    configure_console_encoding()
    args = parse_args()
    run_log = run(
        max_items=args.max_items,
        per_source_limit=args.per_source_limit,
        min_required=args.min_required,
        min_relevance_score=args.min_relevance_score,
        min_per_source=args.min_per_source,
        extract_batch_size=args.extract_batch_size,
        extract_mode=args.extract_mode,
        llm_model=args.llm_model,
        llm_timeout_sec=args.llm_timeout_sec,
        log_level=args.log_level,
    )
    print(json.dumps(run_log, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
