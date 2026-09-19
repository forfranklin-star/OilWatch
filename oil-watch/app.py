# -*- coding: utf-8 -*-
"""原油观察日报 Streamlit 前端：报告阅读、主题树、档案管理、信源清单、说明。"""
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

try:
    for _k, _v in st.secrets.items():
        os.environ.setdefault(_k, str(_v))
except Exception:
    pass

st.set_page_config(page_title="原油观察日报", page_icon="🛢️", layout="wide")
TZ = config.get("REPORT_TZ", "Asia/Shanghai")

st.markdown("""<style>
details:not([data-testid="stExpander"]) {
    border: 1px solid #e8ebf0; border-radius: 10px; padding: 2px 16px;
    margin: 10px 0; background: #fbfcfe;
}
details:not([data-testid="stExpander"]) > summary {
    font-size: 1.06rem; font-weight: 700; padding: 10px 0; cursor: pointer;
}
details:not([data-testid="stExpander"]) details {
    border: none; border-bottom: 1px dashed #edf0f4; border-radius: 0;
    background: transparent; padding: 0; margin: 0;
}
details:not([data-testid="stExpander"]) details > summary {
    font-size: 0.97rem; font-weight: 600; color: #3a3f4a;
    padding: 8px 0 8px 4px;
}
details:not([data-testid="stExpander"]) summary small {
    color: #9aa1ad; font-weight: 400; font-size: 0.80em; margin-left: 6px;
}
details:not([data-testid="stExpander"]) ul {
    margin: 4px 0 10px; padding-left: 20px;
}
details:not([data-testid="stExpander"]) li { margin: 12px 0; }
details:not([data-testid="stExpander"]) li small { color: #9aa1ad; }
details:not([data-testid="stExpander"]) .lk { word-break: break-all; }
details:not([data-testid="stExpander"]) details.dup {
    border: 1px solid #eef1f5 !important; border-radius: 8px;
    background: #f6f8fb; padding: 0 12px; margin: 2px 0 12px;
}
details:not([data-testid="stExpander"]) details.dup > summary {
    font-size: 0.88rem; color: #6b7280; font-weight: 500;
}
table.stattable { border-collapse: collapse; margin: 8px 0; }
table.stattable th, table.stattable td {
    border: 1px solid #e5e7eb; padding: 5px 10px; font-size: 0.92rem;
}
</style>""", unsafe_allow_html=True)


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
        use_feeds=use_feeds, use_prices=use_prices)
    return storage.save_report(rep, report_mod.render_markdown(rep))


def price_metric(col, name, data):
    if not data or data.get("error"):
        col.metric(name, "取数失败")
        return
    delta = data.get("pct_change")
    col.metric(f"{name}（美元/桶）", f"{data.get('close')}",
               None if delta is None else f"{delta}%")


def report_picker(metas, key: str):
    ids = [m["id"] for m in metas]
    idx = 0
    if st.session_state.get("selected_id") in ids:
        idx = ids.index(st.session_state["selected_id"])
    return st.selectbox(
        "选择报告", ids, index=idx, key=key,
        format_func=lambda r: next(f"{m['title']}（{m['item_count']} 条）"
                                   for m in metas if m["id"] == r))


st.sidebar.title("🛢️ 原油观察日报")
st.sidebar.subheader("信源开关")
use_media = st.sidebar.checkbox("全球主流媒体（30 家）", value=True)
use_china = st.sidebar.checkbox("中国国内政经信源（21 个）", value=True)
use_institutions = st.sidebar.checkbox("权威机构（14 家）", value=True)
use_feeds = st.sidebar.checkbox("公共聚合（Google News 等）", value=True)
use_prices = st.sidebar.checkbox("WTI / Brent 价格", value=True)

st.sidebar.subheader("抓取参数")
window_hours = st.sidebar.slider("统计窗口（小时）", 6, 48, 24, step=1)
min_score = st.sidebar.slider(
    "相关性阈值（分）", 1, 10, 5, step=1,
    help="核心油价 3 分；供需/库存/需求/航运/战争/制裁 2 分；宏观/政治 1 分；"
         "且至少命中一个油价直接相关组")

if st.sidebar.button("⚡ 立即生成报告", type="primary", width="stretch"):
    with st.spinner("正在抓取多源内容并生成报告…"):
        rid = generate(window_hours, min_score, use_media, use_china,
                       use_institutions, use_feeds, use_prices)
    st.sidebar.success(f"已生成：{rid}")
    st.session_state["selected_id"] = rid

auto_run = st.sidebar.checkbox("当天 09:08 后无报告时，打开自动补生成", value=False)
st.sidebar.caption("GitHub Actions 每天 09:08（北京时间）自动生成并提交。")

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

with tab_latest:
    metas = storage.list_reports()
    if not metas:
        st.info("还没有存档报告。点击左侧「立即生成报告」，或等待定时任务生成。")
    else:
        chosen = report_picker(metas, key="reader_pick")
        st.session_state["selected_id"] = chosen
        rep = storage.load_report(chosen)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("入选 / 合并组",
                  f"{rep.get('item_count', 0)} / "
                  f"{rep.get('cluster_count', rep.get('item_count', 0))}")
        tc = rep.get("type_counts", {})
        c2.metric("媒体 / 国内 / 机构",
                  f"{tc.get('media', 0)} / {tc.get('china', 0)} / "
                  f"{tc.get('institution', 0)}")
        prices = rep.get("prices") or {}
        price_metric(c3, "WTI", prices.get("WTI"))
        price_metric(c4, "Brent", prices.get("Brent"))
        sec = rep.get("section_counts", {})
        c5.metric("能源 / 地缘条目",
                  f"{sum(v for k, v in sec.items() if k.startswith(('A', 'B')))}")
        st.divider()
        st.markdown(storage.read_markdown(chosen), unsafe_allow_html=True)
        with st.expander("导出 / 下载该报告"):
            st.download_button(
                "⬇ 下载 Markdown",
                data=storage.read_markdown(chosen).encode("utf-8"),
                file_name=f"{chosen}.md", mime="text/markdown")

with tab_tree:
    metas = storage.list_reports()
    if not metas:
        st.info("还没有存档报告。")
    else:
        chosen = report_picker(metas, key="tree_pick")
        rep = storage.load_report(chosen)
        st.caption("门类 → 主题 → 条目；主题内按重要度 + 时效排序，同事件报道已折叠。")
        st.markdown(report_mod.render_toc(rep))
        st.markdown(report_mod.render_tree(rep), unsafe_allow_html=True)

with tab_archive:
    st.caption("报告保存在仓库 reports/ 目录；选中即在页面内显示，管理操作在底部。")
    metas = storage.list_reports()
    if metas:
        st.dataframe(pd.DataFrame([{
            "报告ID": m["id"], "标题": m["title"], "报告日期": m["report_date"],
            "生成时间": m["generated_at"], "条目数": m["item_count"],
            "大小KB": m["size_kb"],
        } for m in metas]), width="stretch", hide_index=True)

        chosen2 = st.selectbox("选择报告", [m["id"] for m in metas],
                               key="archive_pick")
        meta2 = next(m for m in metas if m["id"] == chosen2)
        st.caption(f"{meta2['title']}｜{meta2['generated_at']}｜"
                   f"{meta2['item_count']} 条")
        st.markdown(storage.read_markdown(chosen2), unsafe_allow_html=True)

        with st.expander("导出 / 重命名 / 删除"):
            cc1, cc2, cc3 = st.columns(3)
            cc1.download_button(
                "⬇ 导出 .md", data=storage.read_markdown(chosen2).encode("utf-8"),
                file_name=f"{chosen2}.md", mime="text/markdown", width="stretch")
            cc2.download_button(
                "⬇ 导出 .json",
                data=json.dumps(storage.load_report(chosen2), ensure_ascii=False,
                                indent=2).encode("utf-8"),
                file_name=f"{chosen2}.json", mime="application/json",
                width="stretch")
            cc3.download_button(
                "⬇ 导出 .zip（md+json）", data=storage.export_zip(chosen2),
                file_name=f"{chosen2}.zip", mime="application/zip",
                width="stretch")

            with st.form("rename_form"):
                new_title = st.text_input("新的报告标题", value=meta2["title"])
                if st.form_submit_button("确认重命名"):
                    new_id = storage.rename_report(chosen2, new_title)
                    st.session_state["selected_id"] = new_id
                    st.success(f"已重命名，新 ID：{new_id}")
                    st.rerun()

            if st.button("🗑 删除该报告"):
                st.session_state["confirm_delete"] = chosen2
            if st.session_state.get("confirm_delete") == chosen2:
                st.warning("确认删除？此操作不可恢复。")
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
                "📦 一键导出全部存档（ZIP）", data=storage.export_zip(),
                file_name=f"oilwatch_reports_{now_local().strftime('%Y%m%d_%H%M')}.zip",
                mime="application/zip")
    else:
        st.info("暂无存档。")

with tab_sources:
    st.caption("清单在 data/ 下，可自行增删，用 enabled 列开关。")
    media = media_feeds.load_media(include_disabled=True)
    st.write(f"**全球媒体（共 {len(media)}，启用 {sum(s.enabled for s in media)}）**")
    st.dataframe(pd.DataFrame([{
        "层级": s.tier, "媒体": s.name, "地区": s.region_or_category,
        "Feed数": len(s.feeds), "启用": "是" if s.enabled else "否",
        "主页": s.homepage,
    } for s in media]), width="stretch", hide_index=True)

    china = media_feeds.load_china(include_disabled=True)
    st.write(f"**中国国内政经信源（共 {len(china)}，"
             f"启用 {sum(s.enabled for s in china)}）**")
    st.dataframe(pd.DataFrame([{
        "接入": "官方RSS" if s.tier == "direct" else "GN备份",
        "信源": s.name, "类别": s.region_or_category,
        "Feed数": len(s.feeds), "启用": "是" if s.enabled else "否",
        "主页": s.homepage,
    } for s in china]), width="stretch", hide_index=True)

    insts = media_feeds.load_institutions(include_disabled=True)
    st.write(f"**权威机构（{len(insts)} 家）**")
    st.dataframe(pd.DataFrame([{
        "机构": s.name, "类别": s.region_or_category,
        "Feed数": len(s.feeds), "主页": s.homepage,
    } for s in insts]), width="stretch", hide_index=True)

with tab_help:
    st.subheader("工作机制")
    st.markdown(
        "1. **信源全部免费、无需 Token**：30 家全球主流媒体、21 个中国国内政经信源"
        "（中新网 / 界面 / CGTN 官方 RSS 直连，其余 Google News 站内备份）、"
        "14 家权威机构（OPEC / IEA / EIA / 美联储 / 白宫 / 北约等）。\n"
        "2. **四大门类**：A 能源市场、B 战争与地缘、C 宏观经济、D 政治政策；"
        "纯政治噪音自动剔除。\n"
        "3. **主题树**：门类 → 主题 → 条目三级折叠目录；主题内按重要度 + 时效"
        "综合排序，越新且越相关越靠前。\n"
        "4. **去重折叠**：同一事件的多家报道聚为一组，主报道展示、其余折叠。\n"
        "5. **定时与存档**：GitHub Actions 每天 09:08（北京时间）生成并提交；"
        ".json + .md 成对保存，支持导出 / 重命名 / 删除。")
    st.subheader("数据源自检")
    if st.button("测试 WTI / Brent 价格源"):
        st.json(cached_price_snapshot())
    st.subheader("部署要点")
    st.markdown(
        "- 推送 GitHub 后 Actions 即按计划运行；Streamlit Community Cloud 连接仓库、"
        "入口 `app.py` 部署。\n"
        "- 标记 GN备份 的国内信源依赖 Google News，云端美国机房可达；"
        "中国大陆本地直连会失败并自动跳过，官方 RSS 源不受影响。\n"
        "- 个别信源失败会逐源容错，默认折叠在报告末尾「抓取源状态」中。"
        "详见 README.md。")
