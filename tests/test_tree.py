# -*- coding: utf-8 -*-
"""时效加权排序与主题树渲染测试。"""
import unittest
from datetime import datetime, timedelta, timezone

from oilwatch.pipeline import _recency_bonus
from oilwatch.report import render_toc, render_tree


def _item(cid, score, hours_ago, group="核心油价", section="A 能源市场",
          folded=False):
    now = datetime(2026, 9, 19, 1, 0, tzinfo=timezone.utc)
    created = now - timedelta(hours=hours_ago)
    return {
        "cluster_id": cid, "score": score,
        "rank": round(score + _recency_bonus(created, now), 1),
        "folded": folded, "dup_count": 0,
        "primary_group": group, "primary_section": section,
        "groups": [group], "sections": [section],
        "source_type": "media", "account": "测试社",
        "account_url": "https://example.com", "region": "测试",
        "title": f"标题{cid}", "text": f"标题{cid} crude oil",
        "url": f"https://example.com/{cid}",
        "created_at": created.isoformat(),
        "local_time": created.strftime("%m-%d %H:%M"),
    }


class TestRecency(unittest.TestCase):
    def test_bonus_bands(self):
        now = datetime(2026, 9, 19, tzinfo=timezone.utc)
        self.assertEqual(_recency_bonus(now - timedelta(hours=2), now), 1.5)
        self.assertEqual(_recency_bonus(now - timedelta(hours=10), now), 1.0)
        self.assertEqual(_recency_bonus(now - timedelta(hours=20), now), 0.5)
        self.assertEqual(_recency_bonus(now - timedelta(hours=30), now), 0.0)
        self.assertEqual(_recency_bonus(None, now), 0.0)

    def test_combined_order_newer_wins_within_band(self):
        # 重要度相同：新的在前；重要度差 2 分以上：重要度压过时效
        items = [_item(1, 5, 20), _item(2, 5, 2), _item(3, 8, 20)]
        rep = {"items": items, "main_items": items,
               "section_counts": {"A 能源市场": 3}}
        _, tree, _ = __import__("oilwatch.report", fromlist=["_organize"])._organize(rep)
        order = [i["cluster_id"] for i in tree["A 能源市场"]["核心油价"]]
        self.assertEqual(order, [3, 2, 1])


class TestTreeRender(unittest.TestCase):
    def setUp(self):
        self.rep = {
            "items": [_item(1, 6, 2), _item(2, 3, 5, group="战争冲突",
                                            section="B 战争与地缘")],
            "section_counts": {"A 能源市场": 1, "B 战争与地缘": 1,
                               "C 宏观经济": 0, "D 政治政策": 0},
        }
        self.rep["main_items"] = list(self.rep["items"])

    def test_tree_has_nested_details(self):
        html = render_tree(self.rep)
        self.assertIn("A 能源市场", html)
        self.assertIn("核心油价", html)
        self.assertIn("战争冲突", html)
        self.assertIn("<details", html)
        self.assertIn("最高 6 分", html)

    def test_toc_is_tree_text(self):
        toc = render_toc(self.rep)
        self.assertIn("📂", toc)
        self.assertIn("├─ 核心油价", toc)
        self.assertIn("A 能源市场", toc)


if __name__ == "__main__":
    unittest.main()
