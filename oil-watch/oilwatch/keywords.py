# -*- coding: utf-8 -*-
"""原油影响因素关键词体系（中英双语）。

四大门类（SECTIONS）：
  A 能源市场：核心油价/供需产量/库存炼厂/需求消费/航运油轮/天然气成品油
  B 战争与地缘：战争冲突/制裁与地缘博弈
  C 宏观经济：经济金融（央行、美元、衰退等）
  D 政治政策：政治政策（仅作为加权背景，单独命中不足以入选）

weight: 该组命中首个关键词的基础分；同组每多命中一个词再加 1 分。
"""

# 组 -> 所属门类
GROUP_SECTION = {
    "核心油价": "A 能源市场",
    "供需产量": "A 能源市场",
    "库存炼厂": "A 能源市场",
    "需求消费": "A 能源市场",
    "航运油轮": "A 能源市场",
    "天然气与成品油": "A 能源市场",
    "战争冲突": "B 战争与地缘",
    "制裁与地缘": "B 战争与地缘",
    "经济金融": "C 宏观经济",
    "政治政策": "D 政治政策",
}

# 除“政治政策”外，其余组都属于油价直接相关组；入选内容至少命中其中一个
MARKET_MOVING = [g for g, s in GROUP_SECTION.items() if g != "政治政策"]

SECTION_ORDER = ["A 能源市场", "B 战争与地缘", "C 宏观经济", "D 政治政策"]

KEYWORD_GROUPS = {
    "核心油价": {
        "weight": 3,
        "terms": [
            "crude", "brent", "wti", "opec", "opec+", "barrel", "bbl",
            "oil price", "crude oil", "west texas", "north sea",
            "oil benchmark", "oil futures", "oil rally", "oil slumps",
            "原油", "油价", "布伦特", "美油", "欧佩克", "石油价格", "每桶",
        ],
    },
    "供需产量": {
        "weight": 2,
        "terms": [
            "production", "output", "supply", "output cut", "production cut",
            "voluntary cut", "supply cut", "shale", "permian", "drilling",
            "rig count", "spare capacity", "exports", "imports", "cargo",
            "pump", "pipeline", "refinery outage", "产量", "减产", "供给",
            "供应", "出口", "进口", "页岩油", "钻机", "产能", "增产", "管道",
        ],
    },
    "库存炼厂": {
        "weight": 2,
        "terms": [
            "inventory", "inventories", "stockpile", "crude stock",
            "gasoline stock", "distillate", "eia", "api weekly", "spr",
            "refinery", "refining", "refinery runs", "throughput",
            "库存", "炼厂", "炼油", "去库", "累库", "补库", "战略石油储备",
        ],
    },
    "需求消费": {
        "weight": 2,
        "terms": [
            "demand", "consumption", "jet fuel", "diesel", "gasoline demand",
            "fuel demand", "oil demand", "energy demand",
            "需求", "消费", "航煤", "柴油", "汽油需求", "用油需求",
        ],
    },
    "航运油轮": {
        "weight": 2,
        "terms": [
            "tanker", "vlcc", "suezmax", "aframax", "freight", "shipping",
            "fleet", "dark fleet", "suez canal", "油轮", "运费", "航运",
            "影子船队", "苏伊士运河",
        ],
    },
    "天然气与成品油": {
        "weight": 1,
        "terms": [
            "natural gas", "natgas", "lng", "propane", "naphtha", "fuel oil",
            "gasoil", "天然气", "液化天然气", "石脑油", "燃料油",
        ],
    },
    "战争冲突": {
        "weight": 2,
        "terms": [
            "war", "warfare", "invasion", "invade", "strike", "airstrike",
            "air strike", "missile", "drone attack", "military", "troops",
            "armed", "conflict", "offensive", "ceasefire", "navy", "blockade",
            "coup", "rebel", "militia", "clash", "escalat", "frontline",
            "战争", "军事", "空袭", "导弹", "无人机袭击", "入侵", "冲突",
            "停火", "部队", "封锁", "政变", "武装", "民兵", "袭击", "交战",
            "战事", "开战",
        ],
    },
    "制裁与地缘": {
        "weight": 2,
        "terms": [
            "sanction", "embargo", "price cap", "tariff", "trade war",
            "geopolit", "russia", "ukraine", "iran", "iranian", "saudi",
            "aramco", "israel", "gaza", "hamas", "hezbollah", "houthi",
            "hormuz", "red sea", "venezuela", "iraq", "libya", "syria",
            "sudan", "korean peninsula", "taiwan", "south china sea",
            "制裁", "禁运", "关税", "贸易战", "俄罗斯", "乌克兰", "伊朗",
            "沙特", "以色列", "加沙", "哈马斯", "胡塞", "红海", "霍尔木兹",
            "委内瑞拉", "伊拉克", "利比亚", "叙利亚", "台海", "南海", "朝鲜半岛",
            "地缘",
        ],
    },
    "经济金融": {
        "weight": 1,
        "terms": [
            "central bank", "fed ", "federal reserve", "ecb", "bank of japan",
            "rate cut", "rate hike", "interest rate", "monetary policy",
            "inflation", "cpi", "ppi", "nonfarm", "payroll", "jobs report",
            "gdp", "recession", "pmi", "dollar", "dxy", "treasury yield",
            "bond yield", "stock market", "wall street", "banking crisis",
            "debt ceiling", "credit crunch", "yuan", "yen", "forex",
            "央行", "美联储", "欧央行", "欧洲央行", "日本央行", "加息", "降息",
            "利率", "货币政策", "通胀", "非农", "就业数据", "衰退", "美元",
            "美债", "国债收益率", "股市", "银行业危机", "债务上限", "人民币",
            "日元", "汇率",
        ],
    },
    "政治政策": {
        "weight": 1,
        "terms": [
            "election", "president", "white house", "congress", "senate",
            "parliament", "government", "policy", "regulation", "legislation",
            "prime minister", "chancellor", "regime", "diplomat", "diplomacy",
            "treaty", "summit", "g7", "g20", "un security council",
            "executive order", "energy policy", "export ban",
            "选举", "总统", "白宫", "国会", "参议院", "众议院", "政府", "政策",
            "监管", "立法", "首相", "总理", "政权", "外交", "条约", "峰会",
            "七国集团", "g20", "联合国安理会", "行政令", "能源政策", "出口禁令",
        ],
    },
}

# 组的展示顺序（按门类）
GROUP_ORDER = list(GROUP_SECTION.keys())
