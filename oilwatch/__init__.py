"""oilwatch —— 原油多源每日动态抓取与报告生成。

模块划分：
- keywords/filter: 原油相关性关键词、四大门类与打分
- cluster: 同事件报道聚类折叠
- sources.media_feeds: 全球媒体/国内信源/权威机构 RSS 抓取（CSV 驱动）
- sources.public_feeds: 公共聚合信源（Google News/OilPrice/EIA）
- prices: WTI/Brent 价格快照
- pipeline: 汇总编排
- report: Markdown 渲染（折叠同事件报道）
- storage: 报告存档/重命名/删除/导出
- cli: 命令行入口（供 GitHub Actions 定时调用）
"""

__version__ = "2.0.0"
