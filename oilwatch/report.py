# -*- coding: utf-8 -*-
"""报告渲染：价格快照、概览与目录、主题树（门类>主题>条目）、抓取源状态。

树与折叠区全部输出 HTML（GitHub / Streamlit / 浏览器均可渲染，不依赖
Markdown-in-HTML 解析），目录用代码块，正文其余部分用 Markdown。
"""
import html
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple

from .keywords import GROUP_ORDER, SECTION_ORDER

SOURCE_LABEL = {"media": "媒体", "china": "国内", "institution": "机构"}
SEC_ICON = {"A 能源市场": "🛢️", "B 战争与地缘": "⚔️",
            "C 宏观经济": "📈", "D 政治政策": "🏛️"}


def _esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


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


def _count_label(groups: int, items: int) -> str:
    return f"{items} 条" if groups == items else f"{groups} 组 / {items} 条"


def _link(name: str, url: str) -> str:
    return f'<a href="{_esc(url)}">{_esc(name)}</a>' if url else _esc(name)


def _item_html(i: dict) -> str:
    tag = SOURCE_LABEL.get(i["source_type"], i["source_type"])
    who = i["account"]
    region = i.get("region")
    if region and region != "聚合":
        who = f"{who}（{region}）"
    text = " ".join(i.get("text", "").split())
    if len(text) > 450:
        text = text[:450] + "…"
    hits = "、".join(i.get("groups", []))
    meta = " · ".join(x for x in
                      [i.get("local_time"), f"重要度 {i['score']} 分", hits] if x)
    url = i.get("url", "")
    return (
        "<li>"
        f"<div><b>{_esc(tag)}｜{_link(who, i.get('account_url') or url)}</b> "
        f"<small>{_esc(meta)}</small></div>"
        f"<div>{_esc(text)}</div>"
        f'<div class="lk"><small>链接：<a href="{_esc(url)}">{_esc(url)}</a>'
        "</small></div></li>")


def _folded_html(folded: List[dict]) -> str:
    if not folded:
        return ""
    lis = "".join(_item_html(j) for j in folded)
    return ('<details class="dup"><summary>📎 另有 '
            f"{len(folded)} 条同事件报道</summary><ul>{lis}</ul></details>")


def _organize(report: dict):
    folded_map = defaultdict(list)
    for i in report["items"]:
        if i.get("folded"):
            folded_map[i["cluster_id"]].append(i)
    main_items = report.get("main_items") or [
        i for i in report["items"] if not i.get("folded")]

    def _key(i):
        ts = -1.0
        if i.get("created_at"):
            try:
                ts = datetime.fromisoformat(i["created_at"]).timestamp()
            except ValueError:
                pass
        return (-float(i.get("rank", i["score"])), -ts)

    tree, totals = {}, {}
    for section in SECTION_ORDER:
        sec = [i for i in main_items if i.get("primary_section") == section]
        sec.sort(key=_key)
        groups = {g: gi for g in GROUP_ORDER
                  if (gi := [i for i in sec if i["primary_group"] == g])}
        tree[section] = groups
        totals[section] = sum(1 for i in report["items"]
                              if i.get("primary_section") == section)
    return folded_map, tree, totals


def _pid(report: dict) -> str:
    """按报告生成时间生成 ASCII 锚点前缀，避免多份报告 id 冲突。"""
    raw = str(report.get("generated_at", "r"))
    return "r" + "".join(ch for ch in raw if ch.isalnum() and ch.isascii())


def render_tree(report: dict, section_open: bool = True) -> str:
    """门类（展开）> 主题（折叠）> 条目；空门类不显示。节点带锚点 id。"""
    folded_map, tree, totals = _organize(report)
    p = _pid(report)
    blocks = []
    for s_idx, (section, groups) in enumerate(tree.items()):
        if not groups:
            continue
        n_groups = sum(len(v) for v in groups.values())
        head = (f'<summary>{SEC_ICON.get(section, "·")} <b>{_esc(section)}</b> '
                f"<small>{_count_label(n_groups, totals[section])}</small></summary>")
        group_html = []
        for group, gi in groups.items():
            g_idx = GROUP_ORDER.index(group)
            group_total = sum(1 for i in report["items"]
                              if i.get("primary_group") == group)
            top_score = max(i["score"] for i in gi)
            latest = max((i.get("local_time", "") for i in gi), default="")
            lis, dups = [], []
            for i in gi:
                lis.append(_item_html(i))
                folded = _folded_html(folded_map.get(i["cluster_id"], []))
                if folded:
                    dups.append(folded)
            group_html.append(
                f'<details id="{p}-grp-{g_idx}">'
                f"<summary>&emsp;&emsp;<b>{_esc(group)}</b> "
                f"<small>{_count_label(len(gi), group_total)} · 最高 {top_score} 分"
                f" · 最新 {latest}</small></summary>"
                f'<ul>{"".join(lis)}</ul>{"".join(dups)}'
                "</details>")
        blocks.append(f'<details class="sec" id="{p}-sec-{s_idx}" open>{head}<div>'
                      + "".join(group_html) + "</div></details>")
    return "\n".join(blocks)


def render_toc(report: dict) -> str:
    """可点击的主题目录：门类/主题均为锚点链接，跳到下方树对应位置。"""
    _, tree, totals = _organize(report)
    p = _pid(report)
    rows = ['<div class="toc"><b>📂 主题目录</b>']
    for s_idx, (section, groups) in enumerate(tree.items()):
        if not groups:
            continue
        n_groups = sum(len(v) for v in groups.values())
        rows.append(
            f'<a class="toc-sec" href="#{p}-sec-{s_idx}">'
            f"{SEC_ICON.get(section, '·')} {_esc(section)} "
            f"<small>{_count_label(n_groups, totals[section])}</small></a>")
        for g, gi in groups.items():
            g_idx = GROUP_ORDER.index(g)
            n = sum(1 for i in report["items"] if i.get("primary_group") == g)
            rows.append(
                f'<a class="toc-grp" href="#{p}-grp-{g_idx}">├─ {_esc(g)} '
                f"<small>{_count_label(len(gi), n)}</small></a>")
    rows.append("</div>")
    return "\n".join(rows)


def _status_block(report: dict) -> str:
    statuses = report["source_status"]
    failed = [s for s in statuses if not s["ok"]]
    summary = [s for s in statuses
               if str(s["source"]).endswith("汇总") or s["source"] == "公共聚合"]
    rows = "".join(
        f"<tr><td>{_esc(s['source'])}</td><td>{'✅' if s['ok'] else '⚠️'}</td>"
        f"<td>{_esc(s['detail'])}</td></tr>" for s in summary)
    rows += "".join(
        f"<tr><td>{_esc(s['source'])}</td><td>⚠️</td>"
        f"<td>{_esc(s['detail'])}</td></tr>" for s in failed[:25])
    if len(failed) > 25:
        rows += f"<tr><td>…</td><td>⚠️</td><td>另有 {len(failed) - 25} 个源失败</td></tr>"
    return (
        "<details>"
        f"<summary>🔌 抓取源状态（{len(failed)} 个源失败，点击展开）</summary>"
        '<table class="stattable"><thead><tr><th>来源</th><th>状态</th>'
        f"<th>说明</th></tr></thead><tbody>{rows}</tbody></table></details>")


def render_markdown(report: dict) -> str:
    lines: List[str] = [f"# {report['title']}", ""]
    lines.append(
        f"> 生成 {report['generated_at']}（{report['timezone']}）｜窗口 "
        f"{report['window_hours']}h（自 {report['window_start']}）｜阈值 "
        f"{report['min_score']} 分｜{report.get('media_total', 0)} 家全球媒体、"
        f"{report.get('china_total', 0)} 个国内信源、"
        f"{report.get('institutions_total', 0)} 家机构")
    lines.append("")

    lines.append("## 一、价格快照（WTI / Brent）")
    lines.append("")
    prices = report.get("prices")
    if prices:
        lines += ["| 品种 | 最新 | 前收 | 涨跌 | 时间 |",
                  "|---|---|---|---|---|",
                  _price_line("WTI 原油", prices.get("WTI", {})),
                  _price_line("Brent 原油", prices.get("Brent", {})), "",
                  f"价格来源：{prices.get('source', '')}"
                  f"（抓取于 {prices.get('fetched_at', '')}）", ""]
    else:
        lines += ["本次未抓取价格。", ""]

    lines.append("## 二、今日概览")
    lines.append("")
    tc = report.get("type_counts", {})
    lines.append(
        f"- 入选 **{report['item_count']} 条**，合并同事件后 "
        f"**{report.get('cluster_count', report['item_count'])} 组**："
        f"媒体 {tc.get('media', 0)}、国内 {tc.get('china', 0)}、"
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
    lines += ["", render_toc(report), ""]

    lines.append("## 三、内容主题树")
    lines.append("")
    lines.append("<small>点击主题展开；主题内按「重要度 + 时效」排序"
                 "（6h 内 +1.5、12h 内 +1.0、24h 内 +0.5）。</small>")
    lines.append("")
    lines.append(render_tree(report))

    lines += ["## 附、抓取源状态", "", _status_block(report), "",
              "---",
              "口径：关键词组打分（核心油价 3、供需/库存/需求/航运/战争/制裁 2、"
              "宏观/政治 1），≥阈值且至少命中一个油价直接相关组才入选；"
              "同事件跨源报道按标题相似度聚类折叠。窗口：媒体 24h、国内 48h、"
              "机构 72h。内容仅供研究参考，不构成投资建议。"]
    return "\n".join(lines)
