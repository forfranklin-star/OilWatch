# -*- coding: utf-8 -*-
"""报告本地存档：保存 / 列表 / 读取 / 重命名 / 删除 / 导出。

每份报告由同名 .json（结构化数据）与 .md（可读报告）组成，
统一存放在 reports/ 目录。文件名即报告 id。
"""
import io
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .config import ROOT

REPORTS_DIR = ROOT / "reports"
_SLUG_RE = re.compile(r"[^\w一-龥\-]+", re.UNICODE)


def reports_dir() -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR


def _slug(text: str, fallback: str = "report") -> str:
    slug = _SLUG_RE.sub("_", (text or "").strip()).strip("_")
    return slug or fallback


def save_report(report: dict, markdown: str, directory: Optional[Path] = None) -> str:
    """保存报告，返回报告 id（文件名主干）。同一分钟重复生成自动加序号。"""
    d = Path(directory) if directory else reports_dir()
    d.mkdir(parents=True, exist_ok=True)
    stamp = datetime.fromisoformat(report["generated_at"]).strftime("%Y-%m-%d_%H%M%S")
    base = stamp
    rid = base
    n = 1
    while (d / f"{rid}.json").exists():
        n += 1
        rid = f"{base}_{n}"
    (d / f"{rid}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (d / f"{rid}.md").write_text(markdown, encoding="utf-8")
    return rid


def list_reports(directory: Optional[Path] = None) -> List[dict]:
    d = Path(directory) if directory else reports_dir()
    out = []
    if not d.exists():
        return out
    for jp in sorted(d.glob("*.json"), reverse=True):
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
        except Exception:
            continue
        rid = jp.stem
        out.append({
            "id": rid,
            "title": data.get("title", rid),
            "report_date": data.get("report_date", ""),
            "generated_at": data.get("generated_at", ""),
            "item_count": data.get("item_count", 0),
            "cluster_count": data.get("cluster_count", data.get("item_count", 0)),
            "json_path": str(jp),
            "md_path": str(jp.with_suffix(".md")),
            "size_kb": round(jp.stat().st_size / 1024, 1),
        })
    out.sort(key=lambda x: x["generated_at"], reverse=True)
    return out


def load_report(rid: str, directory: Optional[Path] = None) -> dict:
    d = Path(directory) if directory else reports_dir()
    safe = Path(rid).name  # 防目录穿越
    return json.loads((d / f"{safe}.json").read_text(encoding="utf-8"))


def read_markdown(rid: str, directory: Optional[Path] = None) -> str:
    d = Path(directory) if directory else reports_dir()
    safe = Path(rid).name
    p = d / f"{safe}.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def rename_report(rid: str, new_title: str, directory: Optional[Path] = None) -> str:
    """重命名：修改 JSON 内 title，并把文件名改为新标题的 slug，返回新 id。"""
    d = Path(directory) if directory else reports_dir()
    old = Path(rid).name
    jp = d / f"{old}.json"
    mp = d / f"{old}.md"
    data = json.loads(jp.read_text(encoding="utf-8"))
    data["title"] = new_title.strip()
    new_id = _slug(new_title, old)
    target = d / f"{new_id}.json"
    if target.exists() and target != jp:
        k = 2
        while (d / f"{new_id}_{k}.json").exists():
            k += 1
        new_id = f"{new_id}_{k}"
    (d / f"{new_id}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if mp.exists():
        md_text = mp.read_text(encoding="utf-8")
        md_lines = md_text.splitlines()
        if md_lines and md_lines[0].startswith("# "):
            md_lines[0] = f"# {data['title']}"
            md_text = "\n".join(md_lines) + ("\n" if md_text.endswith("\n") else "")
        (d / f"{new_id}.md").write_text(md_text, encoding="utf-8")
    jp.unlink(missing_ok=True)
    mp.unlink(missing_ok=True)
    return new_id


def delete_report(rid: str, directory: Optional[Path] = None) -> None:
    d = Path(directory) if directory else reports_dir()
    safe = Path(rid).name
    (d / f"{safe}.json").unlink(missing_ok=True)
    (d / f"{safe}.md").unlink(missing_ok=True)


def export_zip(rid: Optional[str] = None, directory: Optional[Path] = None) -> bytes:
    """rid 给定时导出单份报告（json+md），否则打包全部存档为 zip。"""
    d = Path(directory) if directory else reports_dir()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if rid:
            safe = Path(rid).name
            for suffix in (".json", ".md"):
                p = d / f"{safe}{suffix}"
                if p.exists():
                    zf.write(p, arcname=p.name)
        else:
            for p in d.glob("*.*"):
                if p.suffix in (".json", ".md"):
                    zf.write(p, arcname=p.name)
    return buf.getvalue()
