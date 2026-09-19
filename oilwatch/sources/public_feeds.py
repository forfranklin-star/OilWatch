# -*- coding: utf-8 -*-
"""公共聚合信源：Google News 主题检索（免key、全球可达）+ 能源垂直站点。

作为 X / 媒体 / 机构之外的兜底骨干，保证任何环境下都有内容。
"""
import calendar
import html
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote

import feedparser

_TAG_RE = re.compile(r"<[^>]+>")

# 主题式 Google News 检索（过去 1 天），覆盖能源/战争/经济/政治各门类
# 元组：名称、查询、hl、gl、ceid（中文用 zh-Hans）
_TOPICS = [
    ("GN 原油市场(英)", "crude oil OR brent OR wti OR opec when:1d", "en-US", "US", "US:en"),
    ("GN 能源供需(英)", "oil supply OR oil demand OR refinery OR oil inventory when:1d", "en-US", "US", "US:en"),
    ("GN 地缘冲突(英)", "oil AND (sanctions OR war OR Middle East OR Russia OR Iran) when:1d", "en-US", "US", "US:en"),
    ("GN 宏观央行(英)", "Federal Reserve OR dollar OR inflation AND oil when:1d", "en-US", "US", "US:en"),
    ("GN 原油(中)", "原油 OR 油价 OR 欧佩克 when:1d", "zh-Hans", "CN", "CN:zh-Hans"),
    ("GN 地缘能源(中)", "石油 AND (制裁 OR 战争 OR 中东 OR 俄罗斯 OR 伊朗) when:1d", "zh-Hans", "CN", "CN:zh-Hans"),
    ("GN 国内政经(中)", "原油 OR 成品油 OR 天然气 AND (发改委 OR 央行 OR 关税 OR 进出口) when:2d",
     "zh-Hans", "CN", "CN:zh-Hans"),
]
_STATIC = [
    ("OilPrice.com", "https://oilprice.com/rss/main"),
    ("EIA Today in Energy", "https://www.eia.gov/rss/todayinenergy.xml"),
]


def _clean(text: str) -> str:
    return html.unescape(_TAG_RE.sub(" ", text or "")).strip()


def _entry_time(entry) -> Optional[datetime]:
    tt = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not tt:
        return None
    return datetime.fromtimestamp(calendar.timegm(tt), tz=timezone.utc)


def fetch_feeds(since_utc: datetime, timeout: int = 15) -> list:
    items = []
    urls = [(name, f"https://news.google.com/rss/search?q={quote(q)}"
                   f"&hl={hl}&gl={gl}&ceid={ceid}")
            for name, q, hl, gl, ceid in _TOPICS]
    urls.extend(_STATIC)
    for name, url in urls:
        try:
            parsed = feedparser.parse(
                url, request_headers={"User-Agent": "oilwatch/1.0"})
        except Exception:
            continue
        for e in parsed.entries:
            published = _entry_time(e)
            if published and published < since_utc - timedelta(hours=2):
                continue
            title = _clean(getattr(e, "title", ""))
            summary = _clean(getattr(e, "summary", ""))[:500]
            items.append({
                "source_type": "media",
                "via": name,
                "account": name,
                "account_url": url,
                "id": getattr(e, "id", None) or getattr(e, "link", None),
                "created_at": published.isoformat() if published else None,
                "text": f"{title}\n{summary}".strip(),
                "title": title,
                "url": getattr(e, "link", None),
                "lang": None,
                "likes": 0, "retweets": 0, "replies": 0, "quotes": 0,
                "region": "聚合", "tier": "backbone",
            })
    return items
