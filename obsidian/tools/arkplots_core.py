"""Shared data layer for the ArkPlots -> Obsidian exporter.

Reads upstream data READ-ONLY. Never write anything outside obsidian/.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

TOOLS_DIR = Path(__file__).resolve().parent
OBSIDIAN_DIR = TOOLS_DIR.parent                      # <repo>/obsidian
PROJECT_ROOT = OBSIDIAN_DIR.parent                   # <repo> (ArkPlots-Graph or arknight-tool-ArkPlots)
VAULT_DIR = OBSIDIAN_DIR / "ArkPlots Vault"


def _resolve_upstream_root() -> Path:
    if (PROJECT_ROOT / "Plotline.json").exists():
        return PROJECT_ROOT
    for sibling_name in ("arknight-tool-ArkPlots", "ArkPlots"):
        cand = PROJECT_ROOT.parent / sibling_name
        if (cand / "Plotline.json").exists():
            return cand
    return PROJECT_ROOT


UPSTREAM_ROOT = _resolve_upstream_root()
USER_DATA_DIR = (PROJECT_ROOT / "user_data") if (PROJECT_ROOT / "user_data").exists() else (OBSIDIAN_DIR / "user_data")

PLOTLINE_PATH = UPSTREAM_ROOT / "Plotline.json"
USER_READ_RECORD_PATH = USER_DATA_DIR / "Read_record.json"
UPSTREAM_READ_RECORD_PATH = UPSTREAM_ROOT / "Read_record.json"
READ_RECORD_PATH = USER_READ_RECORD_PATH if USER_READ_RECORD_PATH.exists() else UPSTREAM_READ_RECORD_PATH
COVERS_SRC = (UPSTREAM_ROOT / "web" / "public" / "covers") if (UPSTREAM_ROOT / "web" / "public" / "covers").exists() else (UPSTREAM_ROOT / "web" / "dist" / "covers")

PLOTS_FOLDER = "Plots"      # vault-relative
COVERS_FOLDER = "Covers"    # vault-relative

STATUSES = ("未读", "计划读", "正在读", "已读")
READ = "已读"
# JSON Canvas preset colors: 1 red, 2 orange, 3 yellow, 4 green, 5 cyan, 6 purple
STATUS_COLOR = {"已读": "4", "正在读": "2", "计划读": "3"}   # 未读 -> no color
NECESSARY_EDGE_COLOR = "1"
OPTIONAL_EDGE_COLOR = "6"

USER_MARKER = "%% ARKPLOTS:USER %%"

# Fields exported as nested tags so they appear as tag nodes in Obsidian's Graph view.
# new_operator is intentionally excluded: 328 values that each occur once -> isolated leaf nodes.
TAG_FIELDS = (
    ("country", "国家"),
    ("related_power", "势力"),
    ("related_plot", "要素"),
)
# Classification tags (also graph hubs). Set to False to keep the graph focused on the fields above.
CLASS_STAGE_TAGS = True


def tag_value(value: str) -> str:
    """Make a string safe as an Obsidian tag segment (unicode letters/digits, _ and - only)."""
    return "".join(ch if (ch.isalnum() or ch in "_-") else "_" for ch in str(value).strip()) or "_"


def plot_tags(plot: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    if CLASS_STAGE_TAGS:
        tags += [f"类型/{tag_value(plot['class'])}", f"阶段/S{plot['plot_stage']}"]
    for field, prefix in TAG_FIELDS:
        for v in plot.get(field) or []:
            t = f"{prefix}/{tag_value(v)}"
            if t not in tags:
                tags.append(t)
    return tags

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _assert_inside_obsidian(path: Path) -> None:
    p = Path(path).resolve()
    if OBSIDIAN_DIR.resolve() not in (p, *p.parents):
        raise RuntimeError(f"Refusing to write outside obsidian/: {p}")


def load_plots() -> tuple[List[Dict[str, Any]], List[str]]:
    """Return (plots, anomalies).

    Each plot is a shallow copy of the upstream entry with:
      - necessary_plot / optional_plot: only entries that have an 'id' found in the data
      - Videos: upstream videos + any {name,url} objects misplaced in prerequisite lists
    Upstream data is never modified.
    """
    raw = json.loads(PLOTLINE_PATH.read_text(encoding="utf-8"))["data"]
    ids = {p["id"] for p in raw}
    anomalies: List[str] = []
    plots: List[Dict[str, Any]] = []
    for src in raw:
        p = dict(src)
        videos = list(p.get("Videos") or [])
        for key in ("necessary_plot", "optional_plot"):
            clean = []
            seen = set()
            for e in p.get(key) or []:
                if "id" in e and e["id"] in ids:
                    if e["id"] == p["id"]:
                        anomalies.append(f"{p['id']} {p['name']}: self-reference in {key} dropped ({e.get('reason', '')})")
                    elif e["id"] in seen:
                        anomalies.append(f"{p['id']} {p['name']}: duplicate {key} entry for id {e['id']} dropped ({e.get('reason', '')})")
                    else:
                        seen.add(e["id"])
                        clean.append(e)
                elif "url" in e:
                    videos.append({"name": e.get("name", ""), "url": e["url"]})
                    anomalies.append(f"{p['id']} {p['name']}: video object in {key} moved to Videos ({e.get('url')})")
                else:
                    anomalies.append(f"{p['id']} {p['name']}: dropped invalid {key} entry {e!r}")
            p[key] = clean
        p["Videos"] = videos
        for k in ("country", "related_plot", "related_power", "new_operator"):
            p[k] = list(p.get(k) or [])
        p["chapter"] = p.get("chapter") or ""
        plots.append(p)
    return plots, anomalies


def resolve_read_record_path() -> Path:
    """Prefer isolated user reading record under obsidian/user_data/Read_record.json."""
    return USER_READ_RECORD_PATH if USER_READ_RECORD_PATH.exists() else UPSTREAM_READ_RECORD_PATH


def load_status(plots: List[Dict[str, Any]], record_path: Path | None = None) -> Dict[int, str]:
    """Map plot id -> status (default 未读). Read-only."""
    target = Path(record_path) if record_path is not None else resolve_read_record_path()
    data: Dict[str, str] = {}
    if target.exists():
        txt = target.read_text(encoding="utf-8").strip()
        if txt:
            raw = json.loads(txt)
            if isinstance(raw, dict):
                data = raw
    out = {}
    for p in plots:
        s = data.get(str(p["id"]), "未读")
        out[p["id"]] = s if s in STATUSES else "未读"
    return out


def note_stem(plot: Dict[str, Any]) -> str:
    """File stem / wikilink target, e.g. '068 孤星'."""
    return f"{plot['id']:03d} {plot['name']}"


def note_relpath(plot: Dict[str, Any]) -> str:
    """Vault-relative path, e.g. 'Plots/068 孤星.md'."""
    return f"{PLOTS_FOLDER}/{note_stem(plot)}.md"


def wikilink(plot: Dict[str, Any], alias: bool = False) -> str:
    stem = note_stem(plot)
    return f"[[{stem}|{plot['name']}]]" if alias else f"[[{stem}]]"


def stable_id(*parts: Any) -> str:
    """Deterministic 16-char lowercase hex id for canvas nodes/edges."""
    h = hashlib.sha1("|".join(str(x) for x in parts).encode("utf-8")).hexdigest()
    return h[:16]


def cover_filename(plot_id: int) -> str | None:
    """Return the cover file name (e.g. '68.png') in COVERS_SRC, or None."""
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        if (COVERS_SRC / f"{plot_id}{ext}").exists():
            return f"{plot_id}{ext}"
    return None


def successors(plots: List[Dict[str, Any]]) -> Dict[int, Dict[str, List[int]]]:
    """id -> {'necessary': [ids that require this], 'optional': [...]} (reverse edges)."""
    out = {p["id"]: {"necessary": [], "optional": []} for p in plots}
    for p in plots:
        for e in p["necessary_plot"]:
            out[e["id"]]["necessary"].append(p["id"])
        for e in p["optional_plot"]:
            out[e["id"]]["optional"].append(p["id"])
    return out


def missing_prereqs(plot: Dict[str, Any], status: Dict[int, str]) -> List[int]:
    """Direct necessary prerequisites not yet 已读."""
    return [e["id"] for e in plot["necessary_plot"] if status.get(e["id"]) != READ]


def write_if_changed(path: Path, text: str) -> bool:
    """Write UTF-8 (no BOM, LF) only when content differs. Returns True if written."""
    path = Path(path)
    _assert_inside_obsidian(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return True


def dump_canvas(nodes: List[dict], edges: List[dict]) -> str:
    return json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False, indent="\t") + "\n"
