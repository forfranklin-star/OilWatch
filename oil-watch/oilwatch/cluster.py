# -*- coding: utf-8 -*-
"""近似重复新闻聚类：同一事件被多家媒体报道时折叠为一组。

特征：拉丁词（小写）+ 中文单字二元组（bigram），用 Jaccard 相似度贪心聚类。
聚类前输入应已按分值/时间排序，每组第一条即代表条目（主条）。
"""
import re
from typing import List

_LATIN_RE = re.compile(r"[a-z0-9$%.]+")
_CJK_RE = re.compile(r"[一-鿿]")
# 来源前缀，如 "Reuters - "、"CNBC: " 等（仅当前缀含拉丁字母/数字才剥离，
# 避免误删"国际油价上涨："这类正常中文冒号标题）
_PREFIX_RE = re.compile(r"^([\w .·-]{2,20})\s*[-–—:：|]\s*")
_HAS_LATIN = re.compile(r"[A-Za-z0-9]")
# 常见无信息量词
_STOP = {"the", "a", "an", "of", "to", "in", "on", "and", "or", "for", "is",
         "are", "as", "at", "by", "with", "from", "after", "says", "said",
         "has", "have", "will", "its", "it", "that", "this"}


def _stem(w: str) -> str:
    """轻量词干化：处理 rises/rise、cuts/cut、announced/announce 等常见词形。"""
    for suf in ("ies", "ing", "ed", "es", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[:-len(suf)]
    return w


def _strip_source_prefix(t: str) -> str:
    m = _PREFIX_RE.match(t)
    if m and _HAS_LATIN.search(m.group(1)):
        return t[m.end():]
    return t


def features(title: str) -> set:
    t = (title or "").lower()
    t = _strip_source_prefix(t)
    feats = set()
    for w in _LATIN_RE.findall(t):
        if w not in _STOP and len(w) > 1:
            feats.add("w:" + _stem(w))
    cjk = _CJK_RE.findall(t)
    for i in range(len(cjk) - 1):
        feats.add("c:" + cjk[i] + cjk[i + 1])
    if len(cjk) == 1:  # 单字中文标题
        feats.add("c:" + cjk[0])
    return feats


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / len(a | b)


_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
_DATE_RE = re.compile(r"\d{1,2}月\d{1,2}日|\d{1,2}日|\d{1,2}/\d{1,2}")
_UP_WORDS = ("上涨", "走高", "攀升", "大涨", "涨", "rise", "rose", "rally",
             "gain", "surge", "jump", "climb")
_DOWN_WORDS = ("下跌", "走低", "下挫", "大跌", "跌", "fall", "fell", "drop",
               "decline", "slump", "plunge", "tumble")


def _numbers(title: str) -> set:
    return set(_NUM_RE.findall(title or ""))


def _polarity(title: str) -> set:
    t = (title or "").lower()
    out = set()
    if any(w in t for w in _UP_WORDS):
        out.add("up")
    if any(w in t for w in _DOWN_WORDS):
        out.add("down")
    return out


def compatible(a_title: str, b_title: str) -> bool:
    """硬约束：日期/数值不一致、涨跌方向相反的两条不算同事件。"""
    da = set(_DATE_RE.findall(a_title or ""))
    db = set(_DATE_RE.findall(b_title or ""))
    if da and db and not (da & db):
        return False
    na, nb = _numbers(a_title), _numbers(b_title)
    if na and nb and not (na & nb):
        return False
    pa, pb = _polarity(a_title), _polarity(b_title)
    if "up" in pa and "down" in pb and "up" not in pb:
        return False
    if "down" in pa and "up" in pb and "down" not in pb:
        return False
    return True


def cluster_items(items: List[dict], threshold: float = 0.5) -> List[dict]:
    """就地给每个 item 写入 cluster_id；返回带 folded/dup_count 标记的列表。

    - 每组第一条 folded=False（主条，dup_count=同组条数-1）；
    - 其余 folded=True（在报告中折叠到主条的 <details> 内）。
    """
    reps: List[tuple] = []  # (cluster_id, feature_set, 代表标题)
    cid = 0
    for item in items:
        title = item.get("title") or item.get("text", "")
        feat = features(title)
        found = None
        for existing_id, rep_feat, rep_title in reps:
            if jaccard(feat, rep_feat) >= threshold and compatible(title, rep_title):
                found = existing_id
                break
        if found is None:
            cid += 1
            found = cid
            reps.append((cid, feat, title))
        item["cluster_id"] = found

    sizes = {}
    for item in items:
        sizes[item["cluster_id"]] = sizes.get(item["cluster_id"], 0) + 1

    first_seen = set()
    for item in items:
        c = item["cluster_id"]
        item["folded"] = c in first_seen
        item["dup_count"] = sizes[c] - 1 if c not in first_seen else 0
        first_seen.add(c)
    return items
