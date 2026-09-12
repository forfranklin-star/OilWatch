# -*- coding: utf-8 -*-
"""原油相关性打分、过滤与门类归属。"""
from dataclasses import dataclass, field
from typing import Dict, List

from .keywords import GROUP_SECTION, KEYWORD_GROUPS, MARKET_MOVING


@dataclass
class Score:
    score: int = 0
    groups: List[str] = field(default_factory=list)
    sections: List[str] = field(default_factory=list)
    hits: Dict[str, List[str]] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"score": self.score, "groups": self.groups,
                "sections": self.sections, "hits": self.hits}


def score_text(text: str) -> Score:
    """打分：命中某组第一个词得 weight 分，同组每多一个词 +1。"""
    t = (text or "").lower()
    s = Score()
    for gname, g in KEYWORD_GROUPS.items():
        matched = [term for term in g["terms"] if term.lower() in t]
        if matched:
            s.score += int(g["weight"]) + len(matched) - 1
            s.groups.append(gname)
            s.hits[gname] = matched
    s.sections = sorted({GROUP_SECTION[g] for g in s.groups},
                        key=lambda x: x[0])
    return s


def is_relevant(text: str, min_score: int = 3) -> bool:
    """入选规则（两者同时满足）：
    1) 总分 ≥ min_score（默认3：一个核心油价词，或两个次级主题）；
    2) 至少命中一个油价直接相关组——纯政治/纯泛宏观噪音不入选。
    """
    s = score_text(text)
    return s.score >= min_score and any(g in MARKET_MOVING for g in s.groups)
