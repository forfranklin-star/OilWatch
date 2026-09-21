# -*- coding: utf-8 -*-
"""命令行入口，供 GitHub Actions / 本地 cron 调用。

用法：
  python -m oilwatch.cli daily                # 生成最近24小时日报并存档
  python -m oilwatch.cli daily --window-hours 24 --min-score 5
  python -m oilwatch.cli sources              # 打印媒体/国内/机构信源清单
  python -m oilwatch.cli list                 # 列出已存档报告
"""
import argparse

from . import pipeline, report as report_mod, storage
from .pipeline import DEFAULT_MIN_SCORE
from .sources import media_feeds


def cmd_daily(args) -> int:
    rep = pipeline.run(
        window_hours=args.window_hours,
        min_score=args.min_score,
        use_media=not args.no_media,
        use_china=not args.no_china,
        use_institutions=not args.no_institutions,
        use_feeds=not args.no_feeds,
        use_prices=not args.no_prices,
    )
    md = report_mod.render_markdown(rep)
    rid = storage.save_report(rep, md)
    tc = rep["type_counts"]
    print(f"[ok] 报告已生成: {rid}  入选 {rep['item_count']} 条、"
          f"合并为 {rep['cluster_count']} 组 "
          f"(媒体 {tc.get('media', 0)}/国内 {tc.get('china', 0)}"
          f"/机构 {tc.get('institution', 0)})")
    for s in rep["source_status"]:
        if not s["ok"]:
            print(f"  [warn] {s['source']}: {s['detail']}")
    return 0


def cmd_sources(_args) -> int:
    for label, rows in (("全球媒体", media_feeds.load_media(include_disabled=True)),
                        ("中国国内信源", media_feeds.load_china(include_disabled=True)),
                        ("权威机构", media_feeds.load_institutions(include_disabled=True))):
        print(f"== {label} ==")
        for m in rows:
            flag = " " if m.enabled else "x"
            print(f"[{flag}] {m.tier:<8} {m.name:<24} "
                  f"{m.region_or_category:<10} {len(m.feeds)} feeds")
        print(f"{label}共 {len(rows)}（启用 {sum(m.enabled for m in rows)}）\n")
    return 0


def cmd_list(_args) -> int:
    for meta in storage.list_reports():
        print(f"{meta['id']:<24} {meta['item_count']:>3} 条  {meta['title']}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="oilwatch", description="原油多源每日报告")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_daily = sub.add_parser("daily", help="生成并保存日报")
    p_daily.add_argument("--window-hours", type=int, default=24)
    p_daily.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE)
    p_daily.add_argument("--no-media", action="store_true", help="不抓取全球媒体")
    p_daily.add_argument("--no-china", action="store_true", help="不抓取国内信源")
    p_daily.add_argument("--no-institutions", action="store_true", help="不抓取机构")
    p_daily.add_argument("--no-feeds", action="store_true", help="不抓取聚合骨干")
    p_daily.add_argument("--no-prices", action="store_true", help="不抓取价格")
    p_daily.set_defaults(func=cmd_daily)

    p_src = sub.add_parser("sources", help="打印信源清单")
    p_src.set_defaults(func=cmd_sources)

    p_list = sub.add_parser("list", help="列出存档报告")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
