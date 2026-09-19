# -*- coding: utf-8 -*-
"""每日报告编排：多源抓取 -> 相关性过滤 -> 去重聚类 -> 按门类分组 -> 组装报告。"""
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from . import config
from . import prices as prices_mod
from .cluster import cluster_items
from .filter import score_text
from .keywords import GROUP_SECTION, SECTION_ORDER
from .sources import media_feeds, public_feeds

DEFAULT_TZ = config.get("REPORT_TZ", "Asia/Shanghai")


def get_now(tz_name: str = DEFAULT_TZ) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _recency_bonus(created: Optional[datetime], now_utc: datetime) -> float:
    """时效加分：越新越靠前，但最多 1.5 分，不会越过一个重要度档。

    ≤6h +1.5；≤12h +1.0；≤24h +0.5；更早或无时间戳 0。
    """
    if created is None:
        return 0.0
    age_h = (now_utc - created.astimezone(ZoneInfo("UTC"))).total_seconds() / 3600
    if age_h < 0:  # 时间戳轻微在未来（时钟偏差）按最新处理
        return 1.5
    if age_h <= 6:
        return 1.5
    if age_h <= 12:
        return 1.0
    if age_h <= 24:
        return 0.5
    return 0.0


def run(window_hours: int = 24, min_score: int = 3,
        use_media: bool = True, use_china: bool = True,
        use_institutions: bool = True, use_feeds: bool = True,
        use_prices: bool = True, now: Optional[datetime] = None,
        tz_name: str = DEFAULT_TZ, dup_threshold: float = 0.5) -> dict:
    now = now or get_now(tz_name)
    since = now - timedelta(hours=window_hours)
    tz = ZoneInfo(tz_name)
    since_utc = since.astimezone(ZoneInfo("UTC"))

    media_sources = media_feeds.load_media()
    china_sources = media_feeds.load_china()
    inst_sources = media_feeds.load_institutions()

    statuses = []
    raw_items = []

    def _collect(items, st):
        raw_items.extend(items)
        statuses.extend(st)

    # 1) 全球主流媒体
    if use_media:
        _collect(*media_feeds.fetch_sources(media_sources, "media", since_utc))
    # 2) 中国国内政经信源
    if use_china:
        _collect(*media_feeds.fetch_china(since_utc))
    # 3) 权威机构
    if use_institutions:
        _collect(*media_feeds.fetch_sources(inst_sources, "institution",
                                            since_utc, grace_hours=72))
    # 4) 公共聚合骨干
    if use_feeds:
        try:
            feed_items = public_feeds.fetch_feeds(since_utc)
            raw_items.extend(feed_items)
            statuses.append({"source": "公共聚合", "ok": True,
                             "detail": f"{len(feed_items)} 条聚合条目"})
        except Exception as exc:
            statuses.append({"source": "公共聚合", "ok": False, "detail": str(exc)[:200]})

    price_data = prices_mod.snapshot() if use_prices else None

    # 5) 相关性过滤与打分（按标题精确去重，再做近似聚类折叠）
    kept = []
    dedup_titles = set()
    for item in raw_items:
        sc = score_text(item.get("text", ""))
        if sc.score < min_score:
            continue
        if not any(g != "政治政策" for g in sc.groups):
            continue  # 纯政治噪音不入选
        title_key = (item.get("title") or item.get("text", ""))[:60].lower()
        if title_key and title_key in dedup_titles:
            continue
        dedup_titles.add(title_key)
        item = dict(item)
        item["score"] = sc.score
        item["groups"] = sc.groups
        item["sections"] = sc.sections
        item["hits"] = sc.hits
        item["primary_group"] = sc.groups[0]
        item["primary_section"] = GROUP_SECTION.get(item["primary_group"], "其他")
        created = _parse_dt(item.get("created_at"))
        item["local_time"] = (created.astimezone(tz).strftime("%m-%d %H:%M")
                              if created else "")
        bonus = _recency_bonus(created, now.astimezone(ZoneInfo("UTC")))
        item["recency_bonus"] = bonus
        item["rank"] = round(sc.score + bonus, 1)  # 综合排序值=重要度+时效
        kept.append(item)

    kept.sort(key=lambda x: (-x["score"], x.get("created_at") or ""))
    cluster_items(kept, threshold=dup_threshold)
    # 主题内排序：综合 rank（重要度+时效）优先，同分按时间新→旧
    kept.sort(key=lambda x: (
        -x["rank"], -x["score"],
        -(datetime.fromisoformat(x["created_at"]).timestamp()
          if x.get("created_at") else 0),
    ))

    section_counts = Counter(i["primary_section"] for i in kept)
    group_counts = Counter(i["primary_group"] for i in kept)
    type_counts = Counter(i["source_type"] for i in kept)
    outlet_counts = Counter(i["account"] for i in kept)
    main_items = [i for i in kept if not i["folded"]]

    report = {
        "schema_version": 4,  # v4: 条目含 rank（重要度+时效），报告改主题树
        "title": f"原油观察日报 {now.strftime('%Y-%m-%d')}",
        "report_date": now.strftime("%Y-%m-%d"),
        "generated_at": now.isoformat(timespec="seconds"),
        "timezone": tz_name,
        "window_hours": window_hours,
        "window_start": since.isoformat(timespec="seconds"),
        "min_score": min_score,
        "prices": price_data,
        "media_total": len(media_sources),
        "china_total": len(china_sources),
        "institutions_total": len(inst_sources),
        "source_status": statuses,
        "item_count": len(kept),
        "cluster_count": len(main_items),
        "section_counts": {s: section_counts.get(s, 0) for s in SECTION_ORDER},
        "group_counts": dict(group_counts),
        "type_counts": dict(type_counts),
        "top_outlets": outlet_counts.most_common(10),
        "items": kept,
        "main_items": main_items,
    }
    return report
