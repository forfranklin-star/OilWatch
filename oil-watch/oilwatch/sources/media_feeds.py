# -*- coding: utf-8 -*-
"""媒体/机构/国内信源 RSS 抓取（由 data/ 下三份 CSV 驱动）。

- 每家信源可配多个栏目 feed（分号分隔），并发抓取但限制并发数避免被封；
- 单个 feed 失败只记录状态、不影响整体；按链接全局去重；
- source_type 区分 media（全球媒体）/ institution（机构）/ china（国内信源）。
"""
import calendar
import csv
import html
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import feedparser
import requests

from ..config import ROOT

_TAG_RE = re.compile(r"<[^>]+>")
HEADERS = {"User-Agent": "Mozilla/5.0 (oilwatch news reader)",
           "Accept": "application/rss+xml, application/xml, text/xml, */*"}


@dataclass
class Source:
    name: str
    region_or_category: str
    feeds: List[str]
    homepage: str
    tier: str
    enabled: bool
    notes: str


def _read_csv(path: Path) -> List[Source]:
    out: List[Source] = []
    if not path.exists():
        return out
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            feeds = [u.strip() for u in (row.get("feeds") or "").split(";") if u.strip()]
            if not feeds:
                continue
            enabled = str(row.get("enabled", "1")).strip().lower() not in ("0", "false", "no")
            out.append(Source(
                name=(row.get("name") or "").strip(),
                region_or_category=(row.get("region") or row.get("category") or "").strip(),
                feeds=feeds,
                homepage=(row.get("homepage") or "").strip(),
                tier=(row.get("tier") or "").strip(),
                enabled=enabled,
                notes=(row.get("notes") or "").strip(),
            ))
    return out


def load_media(include_disabled: bool = False) -> List[Source]:
    rows = _read_csv(ROOT / "data" / "media.csv")
    return [r for r in rows if include_disabled or r.enabled]


def load_institutions(include_disabled: bool = False) -> List[Source]:
    rows = _read_csv(ROOT / "data" / "institutions.csv")
    return [r for r in rows if include_disabled or r.enabled]


def load_china(include_disabled: bool = False) -> List[Source]:
    rows = _read_csv(ROOT / "data" / "china_sources.csv")
    return [r for r in rows if include_disabled or r.enabled]


def _clean(text: str) -> str:
    return html.unescape(_TAG_RE.sub(" ", text or "")).strip()


_URL_DATE_RE = re.compile(r"/(20\d{2})[-/](\d{1,2})[-/](\d{1,2})/")


def _entry_time(entry, link: str = "") -> Optional[datetime]:
    tt = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not tt and hasattr(entry, "get"):
        tt = entry.get("published_parsed") or entry.get("updated_parsed")
    if tt:
        return datetime.fromtimestamp(calendar.timegm(tt), tz=timezone.utc)
    # 兜底：部分官方 feed 无日期字段，从文章 URL /YYYY-MM/DD/ 提取
    m = _URL_DATE_RE.search(link or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _field(entry, name, default=""):
    val = getattr(entry, name, None)
    if val is None and hasattr(entry, "get"):
        val = entry.get(name)
    return val if val is not None else default


def _fetch_feed(url: str, timeout: int = 10) -> Tuple[list, Optional[str]]:
    try:
        resp = requests.get(url, timeout=timeout, headers=HEADERS)
        if resp.status_code != 200:
            return [], f"HTTP {resp.status_code}"
        parsed = feedparser.parse(resp.content)
        return parsed.entries, None
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:80]}"


def _normalize(source: Source, source_type: str, entries, since_utc: datetime,
               seen: set, grace_hours: int = 3) -> List[dict]:
    items = []
    for e in entries:
        link = _field(e, "link", "")
        if not link or link in seen:
            continue
        published = _entry_time(e, link)
        if published and published < since_utc - timedelta(hours=grace_hours):
            continue
        seen.add(link)
        title = _clean(_field(e, "title", ""))
        summary = _clean(_field(e, "summary", ""))[:700]
        items.append({
            "source_type": source_type,
            "via": source.name,
            "account": source.name,
            "account_url": source.homepage,
            "id": link,
            "created_at": published.isoformat() if published else None,
            "text": f"{title}\n{summary}".strip(),
            "title": title,
            "url": link,
            "lang": None,
            "likes": 0, "retweets": 0, "replies": 0, "quotes": 0,
            "region": source.region_or_category,
            "tier": source.tier,
        })
    return items


def fetch_sources(sources: List[Source], source_type: str, since_utc: datetime,
                  workers: int = 8, grace_hours: int = 3
                  ) -> Tuple[List[dict], List[dict]]:
    items: List[dict] = []
    statuses: List[dict] = []
    seen: set = set()
    if not sources:
        return items, statuses

    future_map = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for src in sources:
            for url in src.feeds:
                future_map[pool.submit(_fetch_feed, url)] = (src, url)
        entries_by_source = {s.name: [] for s in sources}
        errors_by_source = {s.name: [] for s in sources}
        for fut in as_completed(future_map):
            src, url = future_map[fut]
            entries, err = fut.result()
            if err:
                errors_by_source[src.name].append(err)
            else:
                entries_by_source[src.name].extend(entries)

    for src in sources:
        got = _normalize(src, source_type, entries_by_source[src.name],
                         since_utc, seen, grace_hours=grace_hours)
        items.extend(got)
        if got or not errors_by_source[src.name]:
            statuses.append({"source": f"{source_type}:{src.name}", "ok": True,
                             "detail": f"{len(got)} 条窗口内内容"})
        else:
            statuses.append({"source": f"{source_type}:{src.name}", "ok": False,
                             "detail": "；".join(
                                 e[:70] for e in errors_by_source[src.name][:2])})
    ok_n = sum(1 for s in statuses if s["ok"])
    statuses.insert(0, {
        "source": f"{source_type} 汇总", "ok": ok_n > 0,
        "detail": f"{ok_n}/{len(sources)} 个源可用，共取得 {len(items)} 条"})
    return items, statuses


def fetch_media(since_utc: datetime):
    return fetch_sources(load_media(), "media", since_utc)


def fetch_institutions(since_utc: datetime):
    # 机构发文频率低，放宽到 72 小时窗口
    return fetch_sources(load_institutions(), "institution", since_utc,
                         grace_hours=72)


def fetch_china(since_utc: datetime):
    # 国内政府机构发文频率低，统一放宽到 48 小时窗口
    return fetch_sources(load_china(), "china", since_utc, grace_hours=48)
