# -*- coding: utf-8 -*-
"""把报告对象渲染成 Markdown（按四大门类组织；同事件报道折叠）。"""
from collections import defaultdict
from typing import List

from .keywords import GROUP_ORDER, SECTION_ORDER

SOURCE_LABEL = {"media": "媒体", "china": "国内", "institution": "机构"}


def _price_line(name: str, d: dict) -> str:
    if not d:
        return f"| {name} | - | - | - | - |"
    if d.get("error"):
        return f"| {name} | 取数失败 | - | - | {d['error']} |"
    arrow = "▲" if (d.get("change") or 0) >= 0 else "▼"
    return (f"| {name} | {d.get('close') if d.get('close') is not None else '-'} | "
            f"{d.get('prev_close') or '-'} | {arrow} "
            f"{d.get('change') if d.get('change') is not None else '-'} "
            f"（{d.get('pct_change') if d.get('pct_change') is not None else '-'}%） | "
            f"{_fmt_date(d.get('date'))} |")


def _fmt_date(value) -> str:
    if not value:
        return "-"
    s = str(value)
    return s[:16].replace("T", " ") if "T" in s else s


def _item_line(i: dict, indent: str = "") -> str:
    tag = SOURCE_LABEL.get(i["source_type"], i["source_type"])
    who = i["account"]
    region = i.get("region")
    if region and region not in ("聚合",):
        who = f"{who}（{region}）"
    url = i.get("account_url") or i.get("url") or ""
    who_md = f"[{who}]({url})" if url else who
    text = " ".join(i.get("text", "").split())
    if len(text) > 450:
        text = text[:450] + "…"
    hits = "、".join(i.get("groups", []))
    pad = "  " if indent else ""
    when = f"{i.get('local_time', '')} " if i.get("local_time") else ""
    return (f"{pad}- **{tag}｜{who_md}** {when}"
            f"（{hits}，{i['score']}分）\n{pad}  {text}\n{pad}  链接：{i.get('url', '')}")


def _folded_block(cluster_id: int, folded: List[dict]) -> List[str]:
    """同事件的其他报道折叠：Markdown/Streamlit/GitHub 均支持 details 标签。"""
    if not folded:
        return []
    lines = ["", "<details>",
             f"<summary>📎 另有 {len(folded)} 条同事件报道（点击展开）</summary>", ""]
    for j in folded:
        lines.append(_item_line(j, indent="fold"))
        lines.append("")
    lines += ["</details>", ""]
    return lines


def render_markdown(report: dict) -> str:
    lines: List[str] = []
    lines.append(f"# {report['title']}")
    lines.append("")
    lines.append(
        f"> 生成：{report['generated_at']}（{report['timezone']}）｜窗口：最近 "
        f"{report['window_hours']} 小时（自 {report['window_start']}）｜阈值："
        f"{report['min_score']} 分｜监控：{report.get('media_total', 0)} 家全球媒体、"
        f"{report.get('china_total', 0)} 个国内信源、"
        f"{report.get('institutions_total', 0)} 家机构")
    lines.append("")

    # 一、价格快照
    lines.append("## 一、价格快照（WTI / Brent）")
    lines.append("")
    prices = report.get("prices")
    if prices:
        lines += ["| 品种 | 最新 | 前收 | 涨跌 | 时间 |",
                  "|---|---|---|---|---|",
                  _price_line("WTI 原油", prices.get("WTI", {})),
                  _price_line("Brent 原油", prices.get("Brent", {})), "",
                  f"价格来源：{prices.get('source', '')}（抓取于 {prices.get('fetched_at', '')}）", ""]
    else:
        lines += ["本次未抓取价格。", ""]

    # 二、概览
    lines.append("## 二、今日概览")
    lines.append("")
    tc = report.get("type_counts", {})
    lines.append(
        f"- 入选相关内容 **{report['item_count']} 条**，同事件合并后为 "
        f"**{report.get('cluster_count', report['item_count'])} 组**："
        f"全球媒体 {tc.get('media', 0)}、国内信源 {tc.get('china', 0)}、"
        f"机构 {tc.get('institution', 0)}")
    sc = report.get("section_counts", {})
    lines.append("- 门类分布：" + "；".join(f"{k} {v}" for k, v in sc.items() if v))
    gc = report.get("group_counts", {})
    if gc:
        lines.append("- 主题分布：" + "；".join(
            f"{g} {n}" for g, n in sorted(gc.items(), key=lambda kv: -kv[1])))
    tops = report.get("top_outlets", [])[:8]
    if tops:
        lines.append("- 高产信源：" + "；".join(f"{n} {c}" for n, c in tops))
    lines.append("")

    # 折叠成员索引：cluster_id -> 其余报道
    folded_map = defaultdict(list)
    for i in report["items"]:
        if i.get("folded"):
            folded_map[i["cluster_id"]].append(i)

    # 三~六、按四大门类分节（主条展示，重复折叠）
    main_items = report.get("main_items") or [
        i for i in report["items"] if not i.get("folded")]
    sec_no = {"A 能源市场": "三", "B 战争与地缘": "四",
              "C 宏观经济": "五", "D 政治政策": "六"}
    for section in SECTION_ORDER:
        sec_items = [i for i in main_items if i.get("primary_section") == section]
        total = sum(1 for i in report["items"]
                    if i.get("primary_section") == section)
        lines.append(f"## {sec_no.get(section, '附')}、{section}"
                     f"（{len(sec_items)} 组 / {total} 条）")
        lines.append("")
        if not sec_items:
            lines.append("_本门类窗口内无达到阈值的内容。_")
            lines.append("")
            continue
        groups_here = [g for g in GROUP_ORDER
                       if any(i["primary_group"] == g for i in sec_items)]
        for group in groups_here:
            gi = [i for i in sec_items if i["primary_group"] == group]
            group_total = sum(1 for i in report["items"]
                              if i["primary_group"] == group)
            lines.append(f"### {group}（{len(gi)} 组 / {group_total} 条）")
            lines.append("")
            for i in gi:
                lines.append(_item_line(i))
                lines.extend(_folded_block(i["cluster_id"],
                                           folded_map.get(i["cluster_id"], [])))
            lines.append("")

    # 附：抓取状态（紧凑表格，只列汇总与失败项）
    lines.append("## 附、抓取源状态")
    lines.append("")
    failed = [s for s in report["source_status"] if not s["ok"]]
    summary = [s for s in report["source_status"]
               if str(s["source"]).endswith("汇总") or s["source"] == "公共聚合"]
    lines.append("| 来源 | 状态 | 说明 |")
    lines.append("|---|---|---|")
    for s in summary:
        lines.append(f"| {s['source']} | {'✅' if s['ok'] else '⚠️'} | {s['detail']} |")
    for s in failed[:25]:
        lines.append(f"| {s['source']} | ⚠️ | {s['detail']} |")
    if len(failed) > 25:
        lines.append(f"| … | ⚠️ | 另有 {len(failed) - 25} 个源失败（详见 JSON） |")
    lines.append("")
    lines.append("---")
    lines.append("口径：关键词组打分（核心油价3、供需/库存/需求/航运/战争/制裁2、"
                 "宏观/政治1），≥阈值且至少命中一个油价直接相关组才入选；"
                 "同一事件跨源报道按标题相似度聚类折叠；全球媒体取 24h 窗口、"
                 "国内信源 48h、机构 72h。内容仅供研究参考，不构成投资建议。")
    return "\n".join(lines)
