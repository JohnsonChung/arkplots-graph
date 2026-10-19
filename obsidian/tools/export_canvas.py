"""Obsidian JSON Canvas exporter for ArkPlots.

Exports:
  - ArkPlots S1.canvas .. ArkPlots S4.canvas (Overview by stage)
  - ArkPlots 骨干.canvas (Main + Sidestory backbone across all stages)
  - ArkPlots 阅读计划.canvas (Reading planDAG rooted at planned/in-progress targets)

Work only inside obsidian/. Upstream data is read-only.
"""
from __future__ import annotations

import argparse
import heapq
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

try:
    from .arkplots_core import (
        VAULT_DIR,
        STATUS_COLOR,
        NECESSARY_EDGE_COLOR,
        OPTIONAL_EDGE_COLOR,
        READ,
        load_plots,
        load_status,
        note_stem,
        note_relpath,
        stable_id,
        write_if_changed,
        dump_canvas,
    )
except (ImportError, ModuleNotFoundError):
    try:
        from obsidian.tools.arkplots_core import (
            VAULT_DIR,
            STATUS_COLOR,
            NECESSARY_EDGE_COLOR,
            OPTIONAL_EDGE_COLOR,
            READ,
            load_plots,
            load_status,
            note_stem,
            note_relpath,
            stable_id,
            write_if_changed,
            dump_canvas,
        )
    except (ImportError, ModuleNotFoundError):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from arkplots_core import (
            VAULT_DIR,
            STATUS_COLOR,
            NECESSARY_EDGE_COLOR,
            OPTIONAL_EDGE_COLOR,
            READ,
            load_plots,
            load_status,
            note_stem,
            note_relpath,
            stable_id,
            write_if_changed,
            dump_canvas,
        )

CANVAS_DIR = VAULT_DIR / "Canvas"

# Layout metrics for Overview canvases
COL_W = 320
NODE_W = 260
NODE_H = 120
ROW_H = 150

LANE_PAD_TOP = 50
LANE_PAD_BOTTOM = 30
LANE_PAD_X = 40
LANE_GAP_Y = 40

STUB_NODE_W = 260
STUB_NODE_H = 70
STUB_STEP_Y = 90
STUB_PAD = 40
STUB_GAP_X = 120

# Layout metrics for Reading Plan canvas
FILE_W = 400
FILE_H = 260
RP_GAP_X = 140
RP_GAP_Y = 60

# Class display names (Simplified Chinese)
CLASS_DISPLAY: Dict[str, str] = {
    "main": "主线",
    "sidestory": "别传",
    "interlude": "插曲",
    "ministory": "故事集",
    "manga": "漫画",
    "anime": "动画",
    "rougelike": "集成战略",
    "RA": "生息演算",
    "other": "其他",
}

# Lane ordering and bucket mappings
LANE_DEFS: List[Tuple[str, Tuple[str, ...]]] = [
    ("主线", ("main",)),
    ("别传", ("sidestory",)),
    ("故事集", ("ministory",)),
    ("集成战略/生息演算", ("rougelike", "RA")),
    ("漫画/动画/其他", ("manga", "anime", "other")),
]


def class_display_name(raw_class: str) -> str:
    """Return Simplified Chinese display name for plot class."""
    return CLASS_DISPLAY.get(raw_class, raw_class)


def compute_canvas_bounds(nodes: List[Dict[str, Any]]) -> Tuple[int, int]:
    """Calculate the bounding width and height in pixels for a canvas."""
    if not nodes:
        return 0, 0
    min_x = min(n["x"] for n in nodes)
    min_y = min(n["y"] for n in nodes)
    max_x = max(n["x"] + n["width"] for n in nodes)
    max_y = max(n["y"] + n["height"] for n in nodes)
    return max_x - min_x, max_y - min_y


def validate_canvas(data: Dict[str, Any]) -> List[str]:
    """Validate JSON Canvas data against JSON Canvas 1.0 spec and layout rules.

    Returns a list of error strings (empty if valid).
    """
    errors: List[str] = []

    # 1. JSON round-trip
    try:
        raw = json.dumps(data, ensure_ascii=False)
        loaded = json.loads(raw)
        if not isinstance(loaded, dict):
            errors.append("Canvas data root must be a dict.")
            return errors
    except Exception as exc:
        errors.append(f"JSON round-trip failed: {exc}")
        return errors

    nodes = data.get("nodes")
    edges = data.get("edges")
    if not isinstance(nodes, list):
        errors.append("'nodes' must be a list.")
        nodes = []
    if not isinstance(edges, list):
        errors.append("'edges' must be a list.")
        edges = []

    # 2. Unique IDs across nodes and edges
    node_ids: Set[str] = set()
    all_ids: Set[str] = set()
    node_index: Dict[str, int] = {}

    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"Node at index {idx} is not a dict.")
            continue
        nid = node.get("id")
        if not nid or not isinstance(nid, str):
            errors.append(f"Node at index {idx} has invalid or missing 'id'.")
            continue
        if nid in all_ids:
            errors.append(f"Duplicate ID found across nodes/edges: {nid}")
        all_ids.add(nid)
        node_ids.add(nid)
        node_index[nid] = idx

    for idx, edge in enumerate(edges):
        if not isinstance(edge, dict):
            errors.append(f"Edge at index {idx} is not a dict.")
            continue
        eid = edge.get("id")
        if not eid or not isinstance(eid, str):
            errors.append(f"Edge at index {idx} has invalid or missing 'id'.")
            continue
        if eid in all_ids:
            errors.append(f"Duplicate ID found across nodes/edges: {eid}")
        all_ids.add(eid)

    # 3. Node fields and attributes
    allowed_types = {"text", "file", "link", "group"}
    allowed_colors = {"1", "2", "3", "4", "5", "6"}

    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        nid = node.get("id", f"node_{idx}")
        ntype = node.get("type")
        if ntype not in allowed_types:
            errors.append(f"Node {nid} has invalid type: {ntype}")

        for coord in ("x", "y", "width", "height"):
            val = node.get(coord)
            if not isinstance(val, int):
                errors.append(f"Node {nid} field '{coord}' must be int, got {val!r}")
            elif coord in ("width", "height") and val <= 0:
                errors.append(f"Node {nid} field '{coord}' must be positive, got {val}")

        if "color" in node:
            color = node["color"]
            if color not in allowed_colors and not (isinstance(color, str) and re.match(r"^#[0-9a-fA-F]{6}$", color)):
                errors.append(f"Node {nid} has invalid color: {color}")

        if ntype == "text" and not isinstance(node.get("text"), str):
            errors.append(f"Text node {nid} missing 'text' string")
        elif ntype == "file" and not isinstance(node.get("file"), str):
            errors.append(f"File node {nid} missing 'file' string")
        elif ntype == "link" and not isinstance(node.get("url"), str):
            errors.append(f"Link node {nid} missing 'url' string")

    # 4. Edge endpoints, sides, colors
    allowed_sides = {"top", "right", "bottom", "left"}
    allowed_ends = {"none", "arrow"}

    for idx, edge in enumerate(edges):
        if not isinstance(edge, dict):
            continue
        eid = edge.get("id", f"edge_{idx}")
        from_node = edge.get("fromNode")
        to_node = edge.get("toNode")
        if from_node not in node_ids:
            errors.append(f"Edge {eid} references non-existent fromNode: {from_node}")
        if to_node not in node_ids:
            errors.append(f"Edge {eid} references non-existent toNode: {to_node}")

        if "fromSide" in edge and edge["fromSide"] not in allowed_sides:
            errors.append(f"Edge {eid} invalid fromSide: {edge['fromSide']}")
        if "toSide" in edge and edge["toSide"] not in allowed_sides:
            errors.append(f"Edge {eid} invalid toSide: {edge['toSide']}")
        if "fromEnd" in edge and edge["fromEnd"] not in allowed_ends:
            errors.append(f"Edge {eid} invalid fromEnd: {edge['fromEnd']}")
        if "toEnd" in edge and edge["toEnd"] not in allowed_ends:
            errors.append(f"Edge {eid} invalid toEnd: {edge['toEnd']}")

        if "color" in edge:
            color = edge["color"]
            if color not in allowed_colors and not (isinstance(color, str) and re.match(r"^#[0-9a-fA-F]{6}$", color)):
                errors.append(f"Edge {eid} has invalid color: {color}")

    # 5. Group containment & z-order
    group_nodes = [n for n in nodes if isinstance(n, dict) and n.get("type") == "group"]
    if group_nodes:
        def contains(g: Dict[str, Any], n: Dict[str, Any]) -> bool:
            return (
                g["x"] <= n["x"]
                and g["y"] <= n["y"]
                and n["x"] + n["width"] <= g["x"] + g["width"]
                and n["y"] + n["height"] <= g["y"] + g["height"]
            )

        def overlaps(g: Dict[str, Any], n: Dict[str, Any]) -> bool:
            return not (
                n["x"] + n["width"] <= g["x"]
                or g["x"] + g["width"] <= n["x"]
                or n["y"] + n["height"] <= g["y"]
                or g["y"] + g["height"] <= n["y"]
            )

        for node in nodes:
            if not isinstance(node, dict) or node.get("type") == "group":
                continue
            nid = node.get("id")
            is_header = "header" in str(nid) or node.get("text", "").startswith("# ")
            if is_header:
                for g in group_nodes:
                    if overlaps(g, node):
                        errors.append(f"Header node {nid} unexpectedly overlaps group {g.get('id')}")
            else:
                inside_any = False
                for g in group_nodes:
                    if overlaps(g, node):
                        if contains(g, node):
                            inside_any = True
                            if node_index[g["id"]] > node_index[nid]:
                                errors.append(f"Group {g['id']} contains node {nid} but appears after it in nodes array")
                        else:
                            errors.append(
                                f"Non-group node {nid} partially overlaps group {g['id']} ('{g.get('label')}') "
                                f"without being fully contained: node=({node['x']},{node['y']},{node['width']},{node['height']}), "
                                f"group=({g['x']},{g['y']},{g['width']},{g['height']})"
                            )
                if not inside_any:
                    errors.append(f"Non-group node {nid} is not inside any group bounds")

    return errors


def build_stage_canvas(
    stage: int,
    plots: List[Dict[str, Any]],
    status: Dict[int, str],
    with_optional: bool,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int]]:
    """Build nodes and edges for ArkPlots S{stage}.canvas."""
    canvas_name = f"ArkPlots S{stage}"
    by_id = {p["id"]: p for p in plots}
    stage_plots = [p for p in plots if p["plot_stage"] == stage]

    # Collect distinct dates
    dates = sorted({p["date"] for p in stage_plots})
    col_map = {d: i for i, d in enumerate(dates)}

    # Lanes
    lane_groups: List[Dict[str, Any]] = []
    plot_nodes: List[Dict[str, Any]] = []

    curr_y = 0
    num_cols = len(dates)
    lane_x = -LANE_PAD_X
    lane_w = (num_cols - 1) * COL_W + NODE_W + 2 * LANE_PAD_X if num_cols > 0 else 400

    for lane_label, class_tuple in LANE_DEFS:
        lane_plots = [p for p in stage_plots if p["class"] in class_tuple]
        if not lane_plots:
            continue

        # Group by date within lane
        by_date: Dict[str, List[Dict[str, Any]]] = {d: [] for d in dates}
        for p in lane_plots:
            by_date[p["date"]].append(p)

        max_stack = max(len(by_date[d]) for d in dates) if dates else 1
        lane_h = LANE_PAD_TOP + (max_stack - 1) * ROW_H + NODE_H + LANE_PAD_BOTTOM

        # Lane group node
        lane_group = {
            "id": stable_id(canvas_name, "lane", lane_label),
            "type": "group",
            "x": lane_x,
            "y": curr_y,
            "width": lane_w,
            "height": lane_h,
            "label": lane_label,
        }
        lane_groups.append(lane_group)

        # Plot text nodes
        for d, d_plots in by_date.items():
            sorted_d_plots = sorted(d_plots, key=lambda x: x["id"])
            col_x = col_map[d] * COL_W
            for s_idx, p in enumerate(sorted_d_plots):
                p_status = status.get(p["id"], "未读")
                node_text = f"**[[{note_stem(p)}|{p['name']}]]**\n{p['date']} · {class_display_name(p['class'])} · {p_status}"
                node_dict: Dict[str, Any] = {
                    "id": stable_id(canvas_name, "plot", p["id"]),
                    "type": "text",
                    "x": col_x,
                    "y": curr_y + LANE_PAD_TOP + s_idx * ROW_H,
                    "width": NODE_W,
                    "height": NODE_H,
                    "text": node_text,
                }
                c = STATUS_COLOR.get(p_status)
                if c:
                    node_dict["color"] = c
                plot_nodes.append(node_dict)

        curr_y += lane_h + LANE_GAP_Y

    # Cross-stage prerequisites (stubs)
    stub_ids: Set[int] = set()
    for p in stage_plots:
        for e in p["necessary_plot"]:
            prereq = by_id.get(e["id"])
            if prereq and prereq["plot_stage"] < stage:
                stub_ids.add(e["id"])
        if with_optional:
            for e in p["optional_plot"]:
                prereq = by_id.get(e["id"])
                if prereq and prereq["plot_stage"] < stage:
                    stub_ids.add(e["id"])

    stub_group_node: Dict[str, Any] | None = None
    stub_nodes: List[Dict[str, Any]] = []

    if stub_ids:
        sorted_stub_ids = sorted(stub_ids, key=lambda x: (by_id[x]["plot_stage"], by_id[x]["date"], x))
        n_stubs = len(sorted_stub_ids)
        stub_group_w = STUB_NODE_W + 2 * STUB_PAD
        stub_group_h = STUB_PAD + (n_stubs - 1) * STUB_STEP_Y + STUB_NODE_H + STUB_PAD
        stub_group_x = lane_x - STUB_GAP_X - stub_group_w
        stub_group_y = 0

        stub_group_node = {
            "id": stable_id(canvas_name, "stub_group"),
            "type": "group",
            "x": stub_group_x,
            "y": stub_group_y,
            "width": stub_group_w,
            "height": stub_group_h,
            "label": "来自前期阶段",
        }

        for idx, pid in enumerate(sorted_stub_ids):
            prereq = by_id[pid]
            p_status = status.get(pid, "未读")
            stub_text = f"↩ S{prereq['plot_stage']} **[[{note_stem(prereq)}|{prereq['name']}]]**"
            s_dict: Dict[str, Any] = {
                "id": stable_id(canvas_name, "stub", pid),
                "type": "text",
                "x": stub_group_x + STUB_PAD,
                "y": stub_group_y + STUB_PAD + idx * STUB_STEP_Y,
                "width": STUB_NODE_W,
                "height": STUB_NODE_H,
                "text": stub_text,
            }
            c = STATUS_COLOR.get(p_status)
            if c:
                s_dict["color"] = c
            stub_nodes.append(s_dict)

    # Edges
    edges: List[Dict[str, Any]] = []
    stage_plot_ids = {p["id"] for p in stage_plots}
    nec_count = 0
    opt_count = 0
    seen_edges: Set[Tuple[str, str, str]] = set()

    for p in stage_plots:
        to_node_id = stable_id(canvas_name, "plot", p["id"])

        # Necessary edges
        for e in p["necessary_plot"]:
            prereq_id = e["id"]
            if prereq_id in stage_plot_ids:
                from_node_id = stable_id(canvas_name, "plot", prereq_id)
            elif prereq_id in stub_ids:
                from_node_id = stable_id(canvas_name, "stub", prereq_id)
            else:
                continue

            edge_key = (from_node_id, to_node_id, "necessary")
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)

            edges.append({
                "id": stable_id(canvas_name, "edge", prereq_id, p["id"], "necessary"),
                "fromNode": from_node_id,
                "fromSide": "right",
                "toNode": to_node_id,
                "toSide": "left",
                "toEnd": "arrow",
                "color": NECESSARY_EDGE_COLOR,
            })
            nec_count += 1

        # Optional edges
        if with_optional:
            for e in p["optional_plot"]:
                prereq_id = e["id"]
                if prereq_id in stage_plot_ids:
                    from_node_id = stable_id(canvas_name, "plot", prereq_id)
                elif prereq_id in stub_ids:
                    from_node_id = stable_id(canvas_name, "stub", prereq_id)
                else:
                    continue

                edge_key = (from_node_id, to_node_id, "optional")
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)

                edges.append({
                    "id": stable_id(canvas_name, "edge", prereq_id, p["id"], "optional"),
                    "fromNode": from_node_id,
                    "fromSide": "right",
                    "toNode": to_node_id,
                    "toSide": "left",
                    "toEnd": "arrow",
                    "color": OPTIONAL_EDGE_COLOR,
                })
                opt_count += 1

    # Header text node
    header_w = 640
    header_h = 140
    min_x = min(lane_x, stub_group_node["x"] if stub_group_node else lane_x)
    header_x = min_x
    header_y = -header_h - 60

    header_text = (
        f"# ArkPlots S{stage} 全图\n\n"
        f"剧情：{len(stage_plots)} 部 | 连线：{len(edges)} 条"
        f"{f'（必要 {nec_count}，可选 {opt_count}）' if with_optional else ''}\n"
        f"图例：绿=已读 · 橙=正在读 · 黄=计划读 · 无色=未读\n"
        f"连线说明：必要前置（红）{ ' · 可选前置（紫）' if with_optional else '' }"
    )
    header_node = {
        "id": stable_id(canvas_name, "header"),
        "type": "text",
        "x": header_x,
        "y": header_y,
        "width": header_w,
        "height": header_h,
        "text": header_text,
    }

    # Order: Groups first, then contained nodes, then header
    nodes: List[Dict[str, Any]] = []
    if stub_group_node:
        nodes.append(stub_group_node)
    nodes.extend(lane_groups)
    if stub_nodes:
        nodes.extend(stub_nodes)
    nodes.extend(plot_nodes)
    nodes.append(header_node)

    counts = {
        "plot_nodes": len(stage_plots),
        "stub_nodes": len(stub_nodes),
        "nodes": len(nodes),
        "edges": len(edges),
        "nec_edges": nec_count,
        "opt_edges": opt_count,
    }
    return nodes, edges, counts


def build_backbone_canvas(
    plots: List[Dict[str, Any]],
    status: Dict[int, str],
    with_optional: bool,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int]]:
    """Build nodes and edges for ArkPlots 骨干.canvas (main + sidestory)."""
    canvas_name = "ArkPlots 骨干"
    by_id = {p["id"]: p for p in plots}
    bb_plots = [p for p in plots if p["class"] in ("main", "sidestory")]
    bb_ids = {p["id"]: p for p in bb_plots}

    # Distinct release dates across backbone
    dates = sorted({p["date"] for p in bb_plots})
    col_map = {d: i for i, d in enumerate(dates)}
    num_cols = len(dates)

    lane_x = -LANE_PAD_X
    lane_w = (num_cols - 1) * COL_W + NODE_W + 2 * LANE_PAD_X

    # Lanes: 主线 and 别传 only
    backbone_lanes = [
        ("主线", ("main",)),
        ("别传", ("sidestory",)),
    ]

    lane_groups: List[Dict[str, Any]] = []
    plot_nodes: List[Dict[str, Any]] = []
    curr_y = 0

    for lane_label, class_tuple in backbone_lanes:
        lane_plots = [p for p in bb_plots if p["class"] in class_tuple]
        by_date: Dict[str, List[Dict[str, Any]]] = {d: [] for d in dates}
        for p in lane_plots:
            by_date[p["date"]].append(p)

        max_stack = max(len(by_date[d]) for d in dates) if dates else 1
        lane_h = LANE_PAD_TOP + (max_stack - 1) * ROW_H + NODE_H + LANE_PAD_BOTTOM

        lane_group = {
            "id": stable_id(canvas_name, "lane", lane_label),
            "type": "group",
            "x": lane_x,
            "y": curr_y,
            "width": lane_w,
            "height": lane_h,
            "label": lane_label,
        }
        lane_groups.append(lane_group)

        for d, d_plots in by_date.items():
            sorted_d_plots = sorted(d_plots, key=lambda x: x["id"])
            col_x = col_map[d] * COL_W
            for s_idx, p in enumerate(sorted_d_plots):
                p_status = status.get(p["id"], "未读")
                node_text = f"**[[{note_stem(p)}|{p['name']}]]**\n{p['date']} · {class_display_name(p['class'])} · {p_status}"
                node_dict: Dict[str, Any] = {
                    "id": stable_id(canvas_name, "plot", p["id"]),
                    "type": "text",
                    "x": col_x,
                    "y": curr_y + LANE_PAD_TOP + s_idx * ROW_H,
                    "width": NODE_W,
                    "height": NODE_H,
                    "text": node_text,
                }
                c = STATUS_COLOR.get(p_status)
                if c:
                    node_dict["color"] = c
                plot_nodes.append(node_dict)

        curr_y += lane_h + LANE_GAP_Y

    total_lanes_h = curr_y - LANE_GAP_Y

    # 4 Background stage group nodes S1..S4 spanning each stage's columns and all lanes
    stage_groups: List[Dict[str, Any]] = []
    stage_col_ranges: Dict[int, Tuple[int, int]] = {}
    for s in (1, 2, 3, 4):
        s_cols = [col_map[p["date"]] for p in bb_plots if p["plot_stage"] == s]
        if s_cols:
            stage_col_ranges[s] = (min(s_cols), max(s_cols))

    # Stage background boundaries
    STAGE_PAD_Y_TOP = 50
    STAGE_PAD_Y_BOTTOM = 40
    stage_y = -STAGE_PAD_Y_TOP
    stage_h = total_lanes_h + STAGE_PAD_Y_TOP + STAGE_PAD_Y_BOTTOM

    # Calculate horizontal boundaries seamlessly between consecutive stages
    # Left edge of S1 aligns with lane_x (-40), right edge of S4 aligns with lane_x + lane_w
    stage_x_bounds: Dict[int, Tuple[int, int]] = {}
    s_keys = sorted(stage_col_ranges.keys())
    for idx, s in enumerate(s_keys):
        c_min, c_max = stage_col_ranges[s]
        if idx == 0:
            left_x = lane_x
        else:
            prev_s = s_keys[idx - 1]
            prev_max_col = stage_col_ranges[prev_s][1]
            # Midpoint between right edge of prev_max_col node and left edge of c_min node
            prev_right_node = prev_max_col * COL_W + NODE_W
            curr_left_node = c_min * COL_W
            left_x = (prev_right_node + curr_left_node) // 2

        if idx == len(s_keys) - 1:
            right_x = lane_x + lane_w
        else:
            next_s = s_keys[idx + 1]
            next_min_col = stage_col_ranges[next_s][0]
            curr_right_node = c_max * COL_W + NODE_W
            next_left_node = next_min_col * COL_W
            right_x = (curr_right_node + next_left_node) // 2

        stage_x_bounds[s] = (left_x, right_x)

    for s in s_keys:
        left_x, right_x = stage_x_bounds[s]
        stage_groups.append({
            "id": stable_id(canvas_name, "stage", f"S{s}"),
            "type": "group",
            "x": left_x,
            "y": stage_y,
            "width": right_x - left_x,
            "height": stage_h,
            "label": f"S{s}",
        })

    # Edges: only where both ends are in main/sidestory
    edges: List[Dict[str, Any]] = []
    nec_count = 0
    opt_count = 0
    seen_edges: Set[Tuple[str, str, str]] = set()

    for p in bb_plots:
        to_node_id = stable_id(canvas_name, "plot", p["id"])
        for e in p["necessary_plot"]:
            prereq_id = e["id"]
            if prereq_id in bb_ids:
                from_node_id = stable_id(canvas_name, "plot", prereq_id)
                edge_key = (from_node_id, to_node_id, "necessary")
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)

                edges.append({
                    "id": stable_id(canvas_name, "edge", prereq_id, p["id"], "necessary"),
                    "fromNode": from_node_id,
                    "fromSide": "right",
                    "toNode": to_node_id,
                    "toSide": "left",
                    "toEnd": "arrow",
                    "color": NECESSARY_EDGE_COLOR,
                })
                nec_count += 1

        if with_optional:
            for e in p["optional_plot"]:
                prereq_id = e["id"]
                if prereq_id in bb_ids:
                    from_node_id = stable_id(canvas_name, "plot", prereq_id)
                    edge_key = (from_node_id, to_node_id, "optional")
                    if edge_key in seen_edges:
                        continue
                    seen_edges.add(edge_key)

                    edges.append({
                        "id": stable_id(canvas_name, "edge", prereq_id, p["id"], "optional"),
                        "fromNode": from_node_id,
                        "fromSide": "right",
                        "toNode": to_node_id,
                        "toSide": "left",
                        "toEnd": "arrow",
                        "color": OPTIONAL_EDGE_COLOR,
                    })
                    opt_count += 1

    # Count omitted edges: total necessary edges with an endpoint outside main/sidestory
    total_nec_in_dataset = sum(len(p["necessary_plot"]) for p in plots)
    omitted_nec_total = total_nec_in_dataset - nec_count
    # Breakdown: how many bb plots have necessary prereqs outside bb
    bb_prereqs_outside = sum(1 for p in bb_plots for e in p["necessary_plot"] if e["id"] not in bb_ids)

    # Header text node
    header_w = 700
    header_h = 160
    header_x = lane_x
    header_y = stage_y - header_h - 60

    header_text = (
        f"# ArkPlots 骨干剧情图（主线与别传）\n\n"
        f"剧情：{len(bb_plots)} 部 | 包含必要前置边：{nec_count} 条"
        f"{f'（可选 {opt_count} 条）' if with_optional else ''}\n"
        f"省略非骨干边：因端点不在主线/别传而略过 {omitted_nec_total} 条必要前置边"
        f"（其中 {bb_prereqs_outside} 条为骨干剧情依赖的非骨干前置）\n"
        f"图例：绿=已读 · 橙=正在读 · 黄=计划读 · 无色=未读\n"
        f"连线说明：必要前置（红）{ ' · 可选前置（紫）' if with_optional else '' }"
    )
    header_node = {
        "id": stable_id(canvas_name, "header"),
        "type": "text",
        "x": header_x,
        "y": header_y,
        "width": header_w,
        "height": header_h,
        "text": header_text,
    }

    # Order: Stage background groups FIRST, then lanes, then plot nodes, then header
    nodes: List[Dict[str, Any]] = []
    nodes.extend(stage_groups)
    nodes.extend(lane_groups)
    nodes.extend(plot_nodes)
    nodes.append(header_node)

    counts = {
        "plot_nodes": len(bb_plots),
        "nodes": len(nodes),
        "edges": len(edges),
        "nec_edges": nec_count,
        "opt_edges": opt_count,
        "omitted_nec": omitted_nec_total,
    }
    return nodes, edges, counts


def build_reading_plan_canvas(
    plots: List[Dict[str, Any]],
    status: Dict[int, str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """Build nodes and edges for ArkPlots 阅读计划.canvas (file nodes, labeled edges)."""
    canvas_name = "ArkPlots 阅读计划"
    by_id = {p["id"]: p for p in plots}

    # Targets: plots with status 计划读 or 正在读
    targets = [p for p in plots if status.get(p["id"]) in ("计划读", "正在读")]

    # Closure: walk necessary prereqs recursively from targets.
    # Traverse THROUGH prereqs that are not 已读.
    # Prereqs that are 已读 are included as reference nodes but not expanded further.
    included: Set[int] = set()
    queue = list(targets)
    visited_expanded: Set[int] = set()
    for t in targets:
        included.add(t["id"])

    while queue:
        curr = queue.pop(0)
        if curr["id"] in visited_expanded:
            continue
        visited_expanded.add(curr["id"])
        for e in curr["necessary_plot"]:
            prereq = by_id.get(e["id"])
            if not prereq:
                continue
            included.add(prereq["id"])
            if status.get(prereq["id"]) != READ:
                if prereq["id"] not in visited_expanded:
                    queue.append(prereq)

    # Compute longest-path depth within this subgraph (prereqs left, targets right)
    prereqs_in_sub = {
        pid: [e["id"] for e in by_id[pid]["necessary_plot"] if e["id"] in included]
        for pid in included
    }

    memo_depth: Dict[int, int] = {}

    def get_layer(pid: int) -> int:
        if pid in memo_depth:
            return memo_depth[pid]
        preds = prereqs_in_sub.get(pid, [])
        if not preds:
            res = 0
        else:
            res = max(get_layer(pred) for pred in preds) + 1
        memo_depth[pid] = res
        return res

    layers = {pid: get_layer(pid) for pid in included}
    max_layer = max(layers.values()) if layers else 0

    # Layout file nodes
    file_nodes: List[Dict[str, Any]] = []
    layer_map: Dict[int, List[int]] = {l: [] for l in range(max_layer + 1)}
    for pid, l in layers.items():
        layer_map[l].append(pid)

    for l in range(max_layer + 1):
        pids_in_l = sorted(layer_map[l], key=lambda x: (by_id[x]["date"], x))
        col_x = l * (FILE_W + RP_GAP_X)
        for s_idx, pid in enumerate(pids_in_l):
            p = by_id[pid]
            p_status = status.get(pid, "未读")
            fn_dict: Dict[str, Any] = {
                "id": stable_id(canvas_name, "file", pid),
                "type": "file",
                "x": col_x,
                "y": s_idx * (FILE_H + RP_GAP_Y),
                "width": FILE_W,
                "height": FILE_H,
                "file": note_relpath(p),
            }
            c = STATUS_COLOR.get(p_status)
            if c:
                fn_dict["color"] = c
            file_nodes.append(fn_dict)

    # Edges: necessary prereq -> dependent among included nodes, with reason label
    edges: List[Dict[str, Any]] = []
    for pid in included:
        p = by_id[pid]
        to_node_id = stable_id(canvas_name, "file", pid)
        for e in p["necessary_plot"]:
            prereq_id = e["id"]
            if prereq_id in included:
                from_node_id = stable_id(canvas_name, "file", prereq_id)
                edges.append({
                    "id": stable_id(canvas_name, "edge", prereq_id, pid, "necessary"),
                    "fromNode": from_node_id,
                    "fromSide": "right",
                    "toNode": to_node_id,
                    "toSide": "left",
                    "toEnd": "arrow",
                    "color": NECESSARY_EDGE_COLOR,
                    "label": e.get("reason", ""),
                })

    # Suggested reading list: topological order of unread nodes in closure
    unread_pids = [pid for pid in included if status.get(pid) != READ]
    in_degrees: Dict[int, int] = {pid: 0 for pid in unread_pids}
    adj: Dict[int, List[int]] = {pid: [] for pid in unread_pids}
    for pid in unread_pids:
        for e in by_id[pid]["necessary_plot"]:
            if e["id"] in in_degrees:
                adj[e["id"]].append(pid)
                in_degrees[pid] += 1

    pq: List[Tuple[str, int]] = [(by_id[pid]["date"], pid) for pid, deg in in_degrees.items() if deg == 0]
    heapq.heapify(pq)

    topo_order: List[Dict[str, Any]] = []
    while pq:
        _, pid = heapq.heappop(pq)
        topo_order.append(by_id[pid])
        for neighbor in adj[pid]:
            in_degrees[neighbor] -= 1
            if in_degrees[neighbor] == 0:
                heapq.heappush(pq, (by_id[neighbor]["date"], neighbor))

    # Header text node
    lines = [
        "# ArkPlots 阅读计划",
        "",
        "**阅读指引**：左侧先读，右侧为计划目标。已读剧情（绿色）作为参考前置保留一层，未读前置需补完。",
        "**图例**：🟩 已读（参考前置） · 🟧 正在读 · 🟨 计划目标 · ⬜ 未读（待补前置）",
        "**连线**：红色箭头为必要前置关系，线上标注推荐阅读理由。",
        "",
        f"### 建议阅读顺序（待补全列表，共 {len(topo_order)} 部）",
    ]
    for i, p in enumerate(topo_order, 1):
        lines.append(f"{i}. [[{note_stem(p)}|{p['name']}]]")

    header_text = "\n".join(lines)
    header_w = 840
    header_h = max(240, 160 + len(topo_order) * 24)
    header_x = 0
    header_y = -header_h - 80

    header_node = {
        "id": stable_id(canvas_name, "header"),
        "type": "text",
        "x": header_x,
        "y": header_y,
        "width": header_w,
        "height": header_h,
        "text": header_text,
    }

    nodes: List[Dict[str, Any]] = list(file_nodes)
    nodes.append(header_node)

    counts: Dict[str, Any] = {
        "nodes": len(nodes),
        "file_nodes": len(file_nodes),
        "edges": len(edges),
        "targets": len(targets),
        "closure": len(included),
        "unread_closure": len(unread_pids),
        "topo_order": topo_order,
    }
    return nodes, edges, counts


def export_canvases(
    plots: List[Dict[str, Any]],
    status: Dict[int, str],
    with_optional: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """Export all ArkPlots Obsidian Canvas files.

    Returns dict mapping filename -> canvas details (nodes, edges, written, path, etc.).
    Raises ValueError on validation failure.
    """
    CANVAS_DIR.mkdir(parents=True, exist_ok=True)
    results: Dict[str, Dict[str, Any]] = {}

    canvas_specs: List[Tuple[str, Any]] = [
        ("ArkPlots S1.canvas", lambda: build_stage_canvas(1, plots, status, with_optional)),
        ("ArkPlots S2.canvas", lambda: build_stage_canvas(2, plots, status, with_optional)),
        ("ArkPlots S3.canvas", lambda: build_stage_canvas(3, plots, status, with_optional)),
        ("ArkPlots S4.canvas", lambda: build_stage_canvas(4, plots, status, with_optional)),
        ("ArkPlots 骨干.canvas", lambda: build_backbone_canvas(plots, status, with_optional)),
        ("ArkPlots 阅读计划.canvas", lambda: build_reading_plan_canvas(plots, status)),
    ]

    for filename, builder in canvas_specs:
        nodes, edges, counts = builder()
        canvas_data = {"nodes": nodes, "edges": edges}

        # Validate before writing; raise on errors
        errors = validate_canvas(canvas_data)
        if errors:
            raise ValueError(f"Canvas validation failed for '{filename}':\n  " + "\n  ".join(errors))

        canvas_path = CANVAS_DIR / filename
        canvas_json = dump_canvas(nodes, edges)
        written = write_if_changed(canvas_path, canvas_json)
        w, h = compute_canvas_bounds(nodes)

        res_item: Dict[str, Any] = {
            "path": canvas_path,
            "nodes": len(nodes),
            "edges": len(edges),
            "written": written,
            "width": w,
            "height": h,
        }
        res_item.update(counts)
        results[filename] = res_item

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Export ArkPlots data to Obsidian Canvas files.")
    parser.add_argument(
        "--with-optional",
        action="store_true",
        help="Include optional prerequisite edges in overview canvases.",
    )
    args = parser.parse_args()

    plots, anomalies = load_plots()
    status = load_status(plots)

    print(f"Loaded {len(plots)} plots ({len(anomalies)} anomalies handled).")
    print(f"Exporting canvases (with_optional={args.with_optional})...")

    results = export_canvases(plots, status, with_optional=args.with_optional)

    total_written = sum(1 for r in results.values() if r["written"])
    print(f"Done. {len(results)} canvases processed ({total_written} written/updated):")
    for fname, r in results.items():
        w_status = "WRITTEN" if r["written"] else "UNCHANGED"
        print(f"  [{w_status}] {fname}: {r['nodes']} nodes, {r['edges']} edges ({r['width']}x{r['height']} px)")

    # Print reading plan suggested order sample
    rp_info = results.get("ArkPlots 阅读计划.canvas")
    if rp_info and "topo_order" in rp_info:
        topo = rp_info["topo_order"]
        print(f"\nReading plan suggested order (total {len(topo)}):")
        for i, p in enumerate(topo[:15], 1):
            print(f"  {i:2d}. [[{note_stem(p)}|{p['name']}]] ({status.get(p['id'])}, {p['date']})")


if __name__ == "__main__":
    main()
