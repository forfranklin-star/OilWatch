# -*- coding: utf-8 -*-
"""原油多源每日报告 —— Streamlit 前端。
来源：全球 30 家主流媒体 + 20 个中国国内政经信源 + 14 家权威机构 + 公共聚合 + 价格。
部署：本文件位于仓库根目录，Streamlit Community Cloud 直接选择 app.py。
"""
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from oilwatch import config
from oilwatch import pipeline, report as report_mod, storage
from oilwatch.prices import snapshot as price_snapshot
from oilwatch.sources import media_feeds

# Streamlit Secrets -> 环境变量（目前仅 REPORT_TZ 等可选配置）
try:
    for _k, _v in st.secrets.items():
        os.environ.setdefault(_k, str(_v))
except Exception:
    pass

st.set_page_config(page_title="原油观察日报", page_icon="🛢", layout="wide")
TZ = config.get("REPORT_TZ", "Asia/Shanghai")


def now_local() -> datetime:
    return datetime.now(ZoneInfo(TZ))


@st.cache_data(ttl=300, show_spinner=False)
def cached_price_snapshot():
    return price_snapshot()


def generate(window_hours, min_score, use_media, use_china, use_institutions,
             use_feeds, use_prices) -> str:
    rep = pipeline.run(
        window_hours=window_hours, min_score=min_score,
        use_media=use_media, use_china=use_china,
        use_institutions=use_institutions,
        use_feeds=use_feeds, use_prices=use_prices,
    )
    md = report_mod.render_markdown(rep)
    return storage.save_report(rep, md)


def price_metric(col, name, data):
    if not data or data.get("error"):
        col.metric(name, "取数失败")
        return
    delta = data.get("pct_change")
    col.metric(f"{name}（美元/桶）", f"{data.get('close')}",
               None if delta is None else f"{delta}%")


# ---------------------------------------------------------------- 侧边栏
st.sidebar.title("🛢 原油观察日报")
st.sidebar.subheader("信源开关")
use_media = st.sidebar.checkbox("全球主流媒体（30家）", value=True)
use_china = st.sidebar.checkbox("中国国内政经信源（21个）", value=True)
use_institutions = st.sidebar.checkbox("权威机构（14家）", value=True)
use_feeds = st.sidebar.checkbox("公共聚合（Google News 等）", value=True)
use_prices = st.sidebar.checkbox("WTI/Brent 价格", value=True)

st.sidebar.subheader("抓取参数")
window_hours = st.sidebar.slider("统计窗口（小时）", 6, 48, 24, step=1)
min_score = st.sidebar.slider(
    "相关性阈值（分）", 1, 10, 3, step=1,
    help="核心油价3分；供需/库存/需求/航运/战争/制裁2分；宏观/政治1分；"
         "且至少命中一个油价直接相关组")

if st.sidebar.button("⚡ 立即生成报告", type="primary", width="stretch"):
    with st.spinner("正在抓取多源内容并生成报告…"):
        rid = generate(window_hours, min_score, use_media, use_china,
                       use_institutions, use_feeds, use_prices)
    st.sidebar.success(f"已生成：{rid}")
    st.session_state["selected_id"] = rid

auto_run = st.sidebar.checkbox("打开时若当天 09:08 后无报告则自动补生成", value=False)
st.sidebar.caption("定时由 GitHub Actions 每天 09:08（北京时间）执行并提交仓库。")

if auto_run and not st.session_state.get("auto_ran"):
    today = now_local().strftime("%Y-%m-%d")
    has_today = any(m["report_date"] == today for m in storage.list_reports())
    if not has_today and (now_local().hour, now_local().minute) >= (9, 8):
        with st.spinner("自动补生成今日报告…"):
            rid = generate(window_hours, min_score, use_media, use_china,
                           use_institutions, use_feeds, use_prices)
            st.session_state["selected_id"] = rid
    st.session_state["auto_ran"] = True

tab_latest, tab_tree, tab_archive, tab_sources, tab_help = st.tabs(
    ["📄 报告阅读", "🌳 主题树", "🗄 报告档案", "📰 信源清单", "ℹ️ 说明与部署"])

# ---------------------------------------------------------------- 报告阅读
with tab_latest:
    metas = storage.list_reports()
    if not metas:
        st.info("还没有存档报告。点击左侧「立即生成报告」，或等待 GitHub Actions 定时生成。")
    else:
        ids = [m["id"] for m in metas]
        default_idx = 0
        if st.session_state.get("selected_id") in ids:
            default_idx = ids.index(st.session_state["selected_id"])
        chosen = st.selectbox(
            "选择报告", ids, index=default_idx,
            format_func=lambda r: next(f"{m['title']}（{m['item_count']}条）"
                                       for m in metas if m["id"] == r))
        st.session_state["selected_id"] = chosen
        rep = storage.load_report(chosen)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("入选/合并组",
                  f"{rep.get('item_count', 0)}/{rep.get('cluster_count', rep.get('item_count', 0))}")
        tc = rep.get("type_counts", {})
        c2.metric("媒体/国内/机构",
                  f"{tc.get('media',0)}/{tc.get('china',0)}/{tc.get('institution',0)}")
        prices = rep.get("prices") or {}
        price_metric(c3, "WTI", prices.get("WTI"))
        price_metric(c4, "Brent", prices.get("Brent"))
        sec = rep.get("section_counts", {})
        c5.metric("能源/地缘",
                  f"{sum(v for k, v in sec.items() if k.startswith(('A', 'B')))}")
        st.caption("同事件的多家报道已折叠，点击「📎 另有 N 条同事件报道」展开。")
        st.divider()
        st.markdown(storage.read_markdown(chosen), unsafe_allow_html=True)
        st.download_button(
            "下载该报告 Markdown", data=storage.read_markdown(chosen).encode("utf-8"),
            file_name=f"{chosen}.md", mime="text/markdown")

# ---------------------------------------------------------------- 主题树
with tab_tree:
    metas = storage.list_reports()
    if not metas:
        st.info("还没有存档报告。")
    else:
        ids = [m["id"] for m in metas]
        tree_idx = ids.index(st.session_state["selected_id"]) \
            if st.session_state.get("selected_id") in ids else 0
        tree_chosen = st.selectbox(
            "选择报告", ids, index=tree_idx, key="tree_report",
            format_func=lambda r: next(f"{m['title']}（{m['item_count']}条）"
                                       for m in metas if m["id"] == r))
        tree_rep = storage.load_report(tree_chosen)
        cc1, cc2 = st.columns(2)
        only_nonempty = cc1.checkbox("只显示有内容的门类", value=True)
        open_sections = cc2.checkbox("门类默认全部展开", value=True)
        st.caption("目录层级：门类 → 主题 → 条目；主题内按「重要度 + 时效」综合排序，"
                   "同事件报道折叠在主条目内。")
        st.divider()
        if only_nonempty:
            # 临时把空门类从树中剔除（不修改存档）
            import copy
            tree_rep = copy.deepcopy(tree_rep)
            tree_rep["items"] = [i for i in tree_rep["items"]
                                 if tree_rep.get("section_counts", {})
                                 .get(i.get("primary_section"), 0) > 0]
            tree_rep["main_items"] = [i for i in tree_rep.get("main_items", [])
                                      if tree_rep.get("section_counts", {})
                                      .get(i.get("primary_section"), 0) > 0]
        st.markdown(report_mod.render_toc(tree_rep))
        st.markdown(report_mod.render_tree(tree_rep, section_open=open_sections),
                    unsafe_allow_html=True)

# ---------------------------------------------------------------- 报告档案
with tab_archive:
    st.caption("所有报告保存在仓库 reports/ 目录；可导出到本地、重命名或删除。")
    metas = storage.list_reports()
    if metas:
        df = pd.DataFrame([{
            "报告ID": m["id"], "标题": m["title"], "报告日期": m["report_date"],
            "生成时间": m["generated_at"], "条目数": m["item_count"],
            "大小KB": m["size_kb"],
        } for m in metas])
        st.dataframe(df, width="stretch", hide_index=True)

        st.subheader("单份管理")
        chosen2 = st.selectbox("选择要管理的报告", [m["id"] for m in metas],
                               key="archive_select")
        cc1, cc2, cc3 = st.columns(3)
        meta2 = next(m for m in metas if m["id"] == chosen2)
        cc1.download_button(
            "⬇ 导出 .md", data=storage.read_markdown(chosen2).encode("utf-8"),
            file_name=f"{chosen2}.md", mime="text/markdown", width="stretch")
        cc2.download_button(
            "⬇ 导出 .json",
            data=json.dumps(storage.load_report(chosen2), ensure_ascii=False, indent=2
                            ).encode("utf-8"),
            file_name=f"{chosen2}.json", mime="application/json", width="stretch")
        cc3.download_button(
            "⬇ 导出该份 .zip（md+json）", data=storage.export_zip(chosen2),
            file_name=f"{chosen2}.zip", mime="application/zip", width="stretch")

        with st.form("rename_form"):
            new_title = st.text_input("重命名（新的报告标题）", value=meta2["title"])
            if st.form_submit_button("确认重命名"):
                new_id = storage.rename_report(chosen2, new_title)
                st.session_state["selected_id"] = new_id
                st.success(f"已重命名，新ID：{new_id}")
                st.rerun()

        st.write("")
        if st.button("🗑 删除该报告"):
            st.session_state["confirm_delete"] = chosen2
        if st.session_state.get("confirm_delete") == chosen2:
            st.warning("确认删除？此操作不可恢复（删除前可先导出备份）。")
            cdel1, cdel2 = st.columns(2)
            if cdel1.button("确认删除", type="primary"):
                storage.delete_report(chosen2)
                st.session_state.pop("confirm_delete", None)
                st.rerun()
            if cdel2.button("取消"):
                st.session_state.pop("confirm_delete", None)
                st.rerun()

        st.divider()
        st.download_button(
            "📦 一键导出全部存档（ZIP，下载到本地电脑）",
            data=storage.export_zip(),
            file_name=f"oilwatch_reports_{now_local().strftime('%Y%m%d_%H%M')}.zip",
            mime="application/zip")
    else:
        st.info("暂无存档。")

# ---------------------------------------------------------------- 信源清单
with tab_sources:
    st.caption("三份清单均在 data/ 下，可自行增删、用 enabled 列开关。")
    media = media_feeds.load_media(include_disabled=True)
    st.write(f"**全球媒体（共 {len(media)}，启用 {sum(s.enabled for s in media)}）**")
    st.dataframe(pd.DataFrame([{
        "层级": s.tier, "媒体": s.name, "地区": s.region_or_category,
        "Feed数": len(s.feeds), "启用": "是" if s.enabled else "否", "主页": s.homepage,
    } for s in media]), width="stretch", hide_index=True)

    china = media_feeds.load_china(include_disabled=True)
    st.write(f"**中国国内政经信源（共 {len(china)}，启用 {sum(s.enabled for s in china)}）**")
    st.dataframe(pd.DataFrame([{
        "接入": "官方RSS" if s.tier == "direct" else "GN备份",
        "信源": s.name, "类别": s.region_or_category,
        "Feed数": len(s.feeds), "启用": "是" if s.enabled else "否", "主页": s.homepage,
    } for s in china]), width="stretch", hide_index=True)

    insts = media_feeds.load_institutions(include_disabled=True)
    st.write(f"**权威机构（{len(insts)} 家）**")
    st.dataframe(pd.DataFrame([{
        "机构": s.name, "类别": s.region_or_category,
        "Feed数": len(s.feeds), "主页": s.homepage,
    } for s in insts]), width="stretch", hide_index=True)

# ---------------------------------------------------------------- 说明
with tab_help:
    st.subheader("工作机制")
    st.markdown(
        "1. **三类信源（全部免费、无需 key）**：30 家全球主流媒体、21 个中国国内政经信源"
        "（中新网/界面/CGTN 官方 RSS 直连 + 人民网/新华网/财新/一财/华尔街见闻/政府部门等 "
        "Google News 站内备份）、14 家权威机构（OPEC/IEA/EIA/美联储/白宫/北约等）。\n"
        "2. **四大门类**：A 能源市场、B 战争与地缘、C 宏观经济、D 政治政策；"
        "纯政治噪音自动剔除。\n"
        "3. **主题树目录**：报告按「四大门类 → 10 个主题 → 条目」形成可折叠树状目录"
        "（🌳 主题树 Tab），主题内按重要度+时效综合排序，越新且越相关越靠前。\n"
        "4. **去重折叠**：同一事件被多家媒体报道时聚为一组，主报道直接展示、"
        "其余折叠，点击「📎 另有 N 条同事件报道」展开。\n"
        "5. **定时**：GitHub Actions 每天 09:08（北京时间）生成并提交仓库；网页可随时手动生成。\n"
        "6. **存档**：.json + .md 成对保存，支持导出/重命名/删除。")
    st.subheader("数据源自检")
    if st.button("测试 WTI/Brent 价格源"):
        st.json(cached_price_snapshot())
    st.subheader("部署要点")
    st.markdown(
        "- 全部信源免费，无需任何 Token；推送到 GitHub 后 Actions 即按计划运行。\n"
        "- Streamlit Community Cloud 连接仓库、入口 `app.py` 部署。\n"
        "- 国内信源中标记 GN备份 的条目依赖 Google News，云端（美国机房）可达；"
        "在中国大陆本地直连时这些备份会失败并被跳过，官方 RSS 行不受影响。\n"
        "- 个别媒体 RSS 失败会逐源容错并在报告末尾列出状态。详见 README.md。")
