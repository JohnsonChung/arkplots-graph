"""Regenerate the whole ArkPlots Obsidian vault.

Usage (from the project root or anywhere):
    python obsidian/tools/run_all.py [--with-optional]

Reads Plotline.json / Read_record.json / web/public/covers read-only and
writes only inside obsidian/ArkPlots Vault/.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import arkplots_core as core  # noqa: E402
from export_canvas import export_canvases  # noqa: E402
from export_notes import export_notes  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="ArkPlots -> Obsidian vault exporter")
    ap.add_argument("--with-optional", action="store_true", help="also draw optional-prerequisite edges on overview canvases")
    args = ap.parse_args()

    plots, anomalies = core.load_plots()
    status = core.load_status(plots)
    print(f"plots={len(plots)} anomalies={len(anomalies)} vault={core.VAULT_DIR}")
    for a in anomalies:
        print("  !", a)

    print("notes:", export_notes(plots, status, anomalies))
    for name, r in export_canvases(plots, status, with_optional=args.with_optional).items():
        print(f"canvas: {name}: nodes={r['nodes']} edges={r['edges']} written={r['written']} size={r['width']}x{r['height']}")


if __name__ == "__main__":
    main()
