# -*- coding: utf-8 -*-
"""过滤、门类、聚类折叠与信源清单测试：python -m unittest discover -s tests"""
import unittest

from oilwatch.cluster import cluster_items, features, jaccard
from oilwatch.filter import is_relevant, score_text
from oilwatch.keywords import GROUP_SECTION, KEYWORD_GROUPS
from oilwatch.sources.media_feeds import (load_china, load_institutions,
                                          load_media)


class TestFilter(unittest.TestCase):
    def test_core_keyword_passes(self):
        text = "Brent crude jumped after OPEC+ announced a new output cut."
        s = score_text(text)
        self.assertIn("核心油价", s.groups)
        self.assertIn("A 能源市场", s.sections)
        self.assertTrue(is_relevant(text))

    def test_chinese_text(self):
        text = "今日原油价格上涨，布伦特原油突破每桶80美元，欧佩克减产。"
        self.assertGreaterEqual(score_text(text).score, 3)
        self.assertTrue(is_relevant(text))

    def test_irrelevant_text(self):
        self.assertFalse(is_relevant("Great coffee at the office this morning."))

    def test_two_secondary_themes_pass(self):
        text = "Tanker freight rates rise as refinery runs recover in Asia."
        s = score_text(text)
        self.assertIn("航运油轮", s.groups)
        self.assertIn("库存炼厂", s.groups)
        self.assertTrue(is_relevant(text))

    def test_pure_politics_rejected(self):
        text = "The president held an election rally in the capital city."
        self.assertEqual(score_text(text).groups, ["政治政策"])
        self.assertFalse(is_relevant(text))

    def test_war_and_politics_pass(self):
        text = ("The president announced new sanctions and missile strikes "
                "as the war over oil exports escalated.")
        s = score_text(text)
        self.assertIn("战争冲突", s.groups)
        self.assertIn("B 战争与地缘", s.sections)
        self.assertTrue(is_relevant(text))

    def test_section_mapping_complete(self):
        for g in KEYWORD_GROUPS:
            self.assertIn(g, GROUP_SECTION)


class TestCluster(unittest.TestCase):
    def test_english_duplicates_fold(self):
        items = [
            {"title": "Oil prices rise after OPEC output cut announced",
             "text": "a", "score": 5},
            {"title": "Oil prices rise after OPEC announced output cuts",
             "text": "b", "score": 4},
            {"title": "Stocks fall on tech earnings miss", "text": "c", "score": 3},
        ]
        cluster_items(items)
        self.assertFalse(items[0]["folded"])
        self.assertEqual(items[0]["dup_count"], 1)
        self.assertTrue(items[1]["folded"])
        self.assertFalse(items[2]["folded"])
        self.assertEqual(items[0]["cluster_id"], items[1]["cluster_id"])
        self.assertNotEqual(items[0]["cluster_id"], items[2]["cluster_id"])

    def test_chinese_duplicates_fold(self):
        items = [
            {"title": "国际油价上涨 欧佩克宣布减产", "text": "a", "score": 5},
            {"title": "国际油价上涨：欧佩克宣布新一轮减产", "text": "b", "score": 4},
        ]
        cluster_items(items)
        self.assertEqual(items[0]["cluster_id"], items[1]["cluster_id"])
        self.assertTrue(items[1]["folded"])

    def test_different_dates_not_merged(self):
        items = [
            {"title": "纽约油价12日上涨", "text": "a", "score": 5},
            {"title": "纽约油价13日上涨", "text": "b", "score": 4},
        ]
        cluster_items(items)
        self.assertNotEqual(items[0]["cluster_id"], items[1]["cluster_id"])

    def test_daily_series_dates_not_merged(self):
        items = [
            {"title": "人民币市场汇价（12月13日）", "text": "a", "score": 4},
            {"title": "人民币市场汇价（12月12日）", "text": "b", "score": 4},
        ]
        cluster_items(items)
        self.assertNotEqual(items[0]["cluster_id"], items[1]["cluster_id"])

    def test_opposite_direction_not_merged(self):
        items = [
            {"title": "Oil prices rise after OPEC meeting", "text": "a", "score": 5},
            {"title": "Oil prices fall after OPEC meeting", "text": "b", "score": 4},
        ]
        cluster_items(items)
        self.assertNotEqual(items[0]["cluster_id"], items[1]["cluster_id"])

    def test_features(self):
        self.assertGreater(jaccard(features("Oil rises on OPEC cut"),
                                   features("Oil rose on OPEC cuts")), 0.4)
        self.assertEqual(jaccard(set(), features("x")), 0.0)


class TestSourcesLists(unittest.TestCase):
    def test_top30_media(self):
        media = load_media()
        self.assertEqual(len(media), 30)
        self.assertTrue(all(m.feeds for m in load_media(include_disabled=True)))

    def test_china_sources(self):
        china = load_china()
        self.assertGreaterEqual(len(china), 18)
        names = " ".join(s.name for s in china)
        for must in ("中国新闻网", "界面新闻", "CGTN", "中国政府网", "中国人民银行"):
            self.assertIn(must, names)
        direct = [s for s in china if s.tier == "direct"]
        self.assertGreaterEqual(len(direct), 3)
        # 直连源必须是实测实时的
        self.assertTrue(all(s.name in ("中国新闻网", "界面新闻", "CGTN")
                            for s in direct))

    def test_institutions(self):
        inst = load_institutions()
        self.assertGreaterEqual(len(inst), 10)
        names = " ".join(m.name for m in inst)
        self.assertIn("OPEC", names)
        self.assertIn("Federal Reserve", names)


if __name__ == "__main__":
    unittest.main()
