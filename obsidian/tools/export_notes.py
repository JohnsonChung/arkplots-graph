"""Export ArkPlots data into Obsidian notes, covers, base, and home note.

Only writes inside obsidian/.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure parent directory is on sys.path for direct script execution
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

try:
    from .arkplots_core import (
        COVERS_FOLDER,
        COVERS_SRC,
        PLOTS_FOLDER,
        READ,
        STATUSES,
        USER_MARKER,
        VAULT_DIR,
        cover_filename,
        load_plots,
        load_status,
        missing_prereqs,
        note_stem,
        successors,
        wikilink,
        write_if_changed,
    )
except ImportError:
    from arkplots_core import (
        COVERS_FOLDER,
        COVERS_SRC,
        PLOTS_FOLDER,
        READ,
        STATUSES,
        USER_MARKER,
        VAULT_DIR,
        cover_filename,
        load_plots,
        load_status,
        missing_prereqs,
        note_stem,
        successors,
        wikilink,
        write_if_changed,
    )


def _copy_covers(plots: List[Dict[str, Any]]) -> None:
    """Copy available covers from COVERS_SRC to VAULT_DIR/Covers if missing or changed."""
    covers_dir = VAULT_DIR / COVERS_FOLDER
    covers_dir.mkdir(parents=True, exist_ok=True)
    if not COVERS_SRC.exists():
        return

    for src in COVERS_SRC.iterdir():
        if src.is_file() and src.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            dst = covers_dir / src.name
            if (
                not dst.exists()
                or dst.stat().st_size != src.stat().st_size
                or abs(dst.stat().st_mtime - src.stat().st_mtime) > 1e-3
            ):
                shutil.copy2(src, dst)


def _generate_frontmatter(
    plot: Dict[str, Any],
    status_val: str,
    plots_by_id: Dict[int, Dict[str, Any]],
    status_map: Dict[int, str],
) -> str:
    lines = ["---"]
    lines.append(f"arkplot_id: {plot['id']}")
    lines.append(f"aliases: {json.dumps([plot['name']], ensure_ascii=False)}")
    lines.append(f"class: {json.dumps(plot['class'], ensure_ascii=False)}")
    lines.append(f"plot_stage: {plot['plot_stage']}")
    lines.append(f"date: {plot['date']}")
    lines.append(f"chapter: {json.dumps(plot.get('chapter', ''), ensure_ascii=False)}")
    lines.append(f"country: {json.dumps(plot.get('country', []), ensure_ascii=False)}")
    lines.append(f"related_power: {json.dumps(plot.get('related_power', []), ensure_ascii=False)}")
    lines.append(f"related_plot: {json.dumps(plot.get('related_plot', []), ensure_ascii=False)}")
    lines.append(f"new_operator: {json.dumps(plot.get('new_operator', []), ensure_ascii=False)}")
    lines.append(f"status: {json.dumps(status_val, ensure_ascii=False)}")

    nec_links = [
        f"[[{note_stem(plots_by_id[e['id']])}]]"
        for e in plot.get("necessary_plot", [])
        if e.get("id") in plots_by_id
    ]
    lines.append(f"necessary: {json.dumps(nec_links, ensure_ascii=False)}")

    opt_links = [
        f"[[{note_stem(plots_by_id[e['id']])}]]"
        for e in plot.get("optional_plot", [])
        if e.get("id") in plots_by_id
    ]
    lines.append(f"optional: {json.dumps(opt_links, ensure_ascii=False)}")

    missing = missing_prereqs(plot, status_map)
    missing_count = len(missing)
    prereq_ready = (missing_count == 0)

    lines.append(f"prereq_ready: {'true' if prereq_ready else 'false'}")
    lines.append(f"missing_prereqs: {missing_count}")

    cname = cover_filename(plot["id"])
    if cname:
        lines.append(f"cover: {json.dumps(f'[[Covers/{cname}]]', ensure_ascii=False)}")

    try:
        from .arkplots_core import plot_tags
    except ImportError:
        from arkplots_core import plot_tags
    lines.append(f"tags: {json.dumps(plot_tags(plot), ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines)


def _generate_body(
    plot: Dict[str, Any],
    status_val: str,
    plots_by_id: Dict[int, Dict[str, Any]],
    succ_map: Dict[int, Dict[str, List[int]]],
) -> str:
    blocks: List[str] = []

    # Title
    blocks.append(f"# {plot['name']}")

    # Cover
    cname = cover_filename(plot["id"])
    if cname:
        blocks.append(f"![[Covers/{cname}|300]]")

    # Metadata line
    meta_parts = [plot["date"], plot["class"], f"S{plot['plot_stage']}", status_val]
    chapter = (plot.get("chapter") or "").strip()
    if chapter:
        meta_parts.append(chapter)
    blocks.append(" · ".join(meta_parts))

    # 简介
    desc = (plot.get("description") or "").replace("\r\n", "\n").replace("\\r\\n", "\n").replace("\\n", "\n").strip()
    if desc:
        blocks.append(f"## 简介\n\n{desc}")
    else:
        blocks.append("## 简介")

    # 必要前置
    nec_list = plot.get("necessary_plot", [])
    if nec_list:
        items = []
        for e in nec_list:
            target = plots_by_id[e["id"]]
            link = wikilink(target, alias=True)
            reason = e.get("reason", "").strip()
            if reason:
                items.append(f"- {link} — {reason}")
            else:
                items.append(f"- {link}")
        blocks.append("## 必要前置\n\n" + "\n".join(items))
    else:
        blocks.append("## 必要前置\n\n（无）")

    # 可选前置
    opt_list = plot.get("optional_plot", [])
    if opt_list:
        items = []
        for e in opt_list:
            target = plots_by_id[e["id"]]
            link = wikilink(target, alias=True)
            reason = e.get("reason", "").strip()
            if reason:
                items.append(f"- {link} — {reason}")
            else:
                items.append(f"- {link}")
        blocks.append("## 可选前置\n\n" + "\n".join(items))
    else:
        blocks.append("## 可选前置\n\n（无）")

    # 后续剧情
    succ = succ_map.get(plot["id"], {"necessary": [], "optional": []})
    succ_nec = sorted(succ["necessary"])
    succ_opt = sorted(succ["optional"])
    if succ_nec or succ_opt:
        items = []
        for sid in succ_nec:
            if sid in plots_by_id:
                target = plots_by_id[sid]
                items.append(f"- {wikilink(target, alias=True)}")
        for sid in succ_opt:
            if sid in plots_by_id:
                target = plots_by_id[sid]
                items.append(f"- {wikilink(target, alias=True)}（可选）")
        if items:
            blocks.append("## 后续剧情\n\n" + "\n".join(items))
        else:
            blocks.append("## 后续剧情\n\n（无）")
    else:
        blocks.append("## 后续剧情\n\n（无）")

    # 视频
    videos = plot.get("Videos", [])
    if videos:
        items = []
        for v in videos:
            v_name = v.get("name", "").strip()
            v_url = v.get("url", "").strip()
            items.append(f"- [{v_name}]({v_url})")
        blocks.append("## 视频\n\n" + "\n".join(items))
    else:
        blocks.append("## 视频\n\n（无）")

    return "\n\n".join(blocks)


def _generate_base() -> str:
    return """filters:
  and:
    - 'file.inFolder("Plots")'

properties:
  file.name:
    displayName: "名称"
  arkplot_id:
    displayName: "ID"
  date:
    displayName: "上线日期"
  class:
    displayName: "类别"
  plot_stage:
    displayName: "阶段"
  status:
    displayName: "阅读状态"
  prereq_ready:
    displayName: "前置就绪"
  missing_prereqs:
    displayName: "待补前置数"
  cover:
    displayName: "封面"

views:
  - type: table
    name: "总表"
    order:
      - file.name
      - arkplot_id
      - date
      - class
      - plot_stage
      - status
      - prereq_ready
      - missing_prereqs
    sort:
      - property: arkplot_id
        direction: ASC

  - type: cards
    name: "阅读看板"
    image: cover
    groupBy:
      property: status
      direction: ASC
    order:
      - file.name

  - type: table
    name: "可以开读"
    filters:
      and:
        - 'status != "已读"'
        - 'prereq_ready == true'
    order:
      - file.name
      - date
      - class
      - plot_stage
      - status
    sort:
      - property: date
        direction: ASC

  - type: table
    name: "计划读待补"
    filters:
      and:
        - 'status == "计划读"'
        - 'missing_prereqs > 0'
    order:
      - file.name
      - missing_prereqs
      - date
      - class
      - plot_stage
"""


def _generate_home_note(
    plots: List[Dict[str, Any]],
    status: Dict[int, str],
    anomalies: List[str],
) -> str:
    total = len(plots)
    counts = {s: 0 for s in STATUSES}
    for p in plots:
        counts[status.get(p["id"], "未读")] += 1

    lines = [
        "# ArkPlots 剧情导航",
        "",
        "欢迎使用明日方舟剧情图谱（ArkPlots）Obsidian 知识库。本库同步收录了所有剧情节点、前置依赖关系、阅读状态及官方相关视频。",
        "",
        "## 剧情画布导航",
        "",
        "- 阶段图谱：[[Canvas/ArkPlots S1.canvas|S1]] · [[Canvas/ArkPlots S2.canvas|S2]] · [[Canvas/ArkPlots S3.canvas|S3]] · [[Canvas/ArkPlots S4.canvas|S4]]",
        "- 核心脉络：[[Canvas/ArkPlots 骨干.canvas|骨干]]",
        "- 阅读计划：[[Canvas/ArkPlots 阅读计划.canvas|阅读计划]]",
        "",
        "## 阅读进度概览",
        "",
        f"- 已读：{counts['已读']} / {total}",
        f"- 正在读：{counts['正在读']}",
        f"- 计划读：{counts['计划读']}",
        f"- 未读：{counts['未读']}",
        "",
        "## 推荐阅读（可以开读）",
        "",
        "![[ArkPlots.base#可以开读]]",
        "",
        "## 数据异常",
        "",
    ]

    if anomalies:
        for a in anomalies:
            lines.append(f"- {a}")
    else:
        lines.append("（无）")

    lines.append("")
    return "\n".join(lines)


def export_notes(
    plots: List[Dict[str, Any]],
    status: Dict[int, str],
    anomalies: List[str],
) -> Dict[str, int]:
    """Export plots into Obsidian vault notes, covers, base, and home note.

    Returns stats dict: {'written': int, 'unchanged': int, 'renamed': int, 'orphans': int}.
    """
    # 1. Copy covers
    _copy_covers(plots)

    # Prepare maps
    plots_by_id = {p["id"]: p for p in plots}
    succ_map = successors(plots)
    plots_dir = VAULT_DIR / PLOTS_FOLDER
    plots_dir.mkdir(parents=True, exist_ok=True)

    # 3. Rename handling (id-based scan)
    existing_user_sections: Dict[int, str] = {}
    renamed_count = 0
    orphans_count = 0

    for file_path in sorted(plots_dir.glob("*.md")):
        content = file_path.read_text(encoding="utf-8")
        user_section = None
        if USER_MARKER in content:
            user_section = content.partition(USER_MARKER)[2].replace("\r\n", "\n")

        file_id = None
        m_fm = re.search(r"^arkplot_id:\s*(\d+)", content, re.MULTILINE)
        if m_fm:
            file_id = int(m_fm.group(1))
        else:
            m_stem = re.match(r"^(\d{3})\b", file_path.stem)
            if m_stem:
                file_id = int(m_stem.group(1))

        if file_id is None or file_id not in plots_by_id:
            orphans_count += 1
            continue

        target_plot = plots_by_id[file_id]
        expected_stem = note_stem(target_plot)

        if file_path.stem != expected_stem:
            renamed_count += 1
            if user_section is not None:
                existing_user_sections[file_id] = user_section
            file_path.unlink()
        else:
            if user_section is not None:
                existing_user_sections[file_id] = user_section

    # 2. Write note per plot
    notes_written = 0
    notes_unchanged = 0
    default_user_section = "\n\n## 我的笔记\n\n"

    for plot in plots:
        pid = plot["id"]
        status_val = status.get(pid, "未读")
        fm = _generate_frontmatter(plot, status_val, plots_by_id, status)
        body = _generate_body(plot, status_val, plots_by_id, succ_map)

        top_part = f"{fm}\n\n{body}\n\n"
        user_sec = existing_user_sections.get(pid)
        if user_sec is None:
            user_sec = default_user_section

        full_content = f"{top_part}{USER_MARKER}{user_sec}"
        out_path = plots_dir / f"{note_stem(plot)}.md"

        if write_if_changed(out_path, full_content):
            notes_written += 1
        else:
            notes_unchanged += 1

    # 4. ArkPlots.base
    base_path = VAULT_DIR / "ArkPlots.base"
    base_written = write_if_changed(base_path, _generate_base())

    # 5. ArkPlots 首页.md
    home_path = VAULT_DIR / "ArkPlots 首页.md"
    home_content = _generate_home_note(plots, status, anomalies)
    home_written = write_if_changed(home_path, home_content)

    total_files_written = notes_written + (1 if base_written else 0) + (1 if home_written else 0)
    total_files_unchanged = notes_unchanged + (0 if base_written else 1) + (0 if home_written else 1)

    return {
        "written": notes_written,
        "unchanged": notes_unchanged,
        "renamed": renamed_count,
        "orphans": orphans_count,
        "files_written": total_files_written,
        "files_unchanged": total_files_unchanged,
    }


if __name__ == "__main__":
    plots, anomalies = load_plots()
    status = load_status(plots)
    stats = export_notes(plots, status, anomalies)
    print(
        f"Stats: written={stats['written']}, unchanged={stats['unchanged']}, "
        f"renamed={stats['renamed']}, orphans={stats['orphans']}, "
        f"files_written={stats['files_written']}"
    )
