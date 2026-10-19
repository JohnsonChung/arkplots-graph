# arkplots-graph 架構決策紀錄 (ADR) 與 AI 維護索引 (`v1`)

本目錄採用模組化拆分，將**「為什麼這樣設計（ADR 001～003）」**與**「程式碼怎麼改（AI 維護速查手冊）」**分離，讓後續 AI Agent 與開發者能依任務需求只讀取對應的單一檔案，最大化節省 Context Token 與瀏覽時間。

---

## 🧭 AI Agent 任務導航表（依任務挑選單一檔案閱讀）

| 當你的任務是…… | 請優先閱讀哪一份文件 | 內容摘要 |
| --- | --- | --- |
| **定位某個 Function 行號、查資料型別、查 DOM ID 或修改程式碼** | 👉 [**`AI-MAINTENANCE-GUIDE.md`**](file:///m:/Github/ArkPlots-Graph/docs/adr/AI-MAINTENANCE-GUIDE.md) | `index.html` (`v1` PRTS 預設版) 與 `themes/ArkPlots-Graph-dev.html` (開發簡約版) 9 大行號熱區、核心型別 (`classDiagram`)、JS 與 Python 函式速查表 |
| **了解獨立 Repo 結構、上游零污染規範、跨目錄封面路徑或 `v1` 主題分層 (`PRTS` / `終末地` / `Dev` / `deprecated`)** | [**`ADR-001-arkplots-graph-architecture.md`**](file:///m:/Github/ArkPlots-Graph/docs/adr/ADR-001-arkplots-graph-architecture.md) | 同級並排 Repo (`M:\Github\ArkPlots-Graph`)、預設入口 `theme:PRTS`、開發預覽 `theme:終末地`、開發簡約版 `Dev Minimal` 與 `themes/deprecated/` 封存策略 |
| **修改 `Read_record.json` 綁定、記憶路徑、跨主題共享快取或擴充「雙向寫回」功能** | [**`ADR-002-persistence-and-data-flow.md`**](file:///m:/Github/ArkPlots-Graph/docs/adr/ADR-002-persistence-and-data-flow.md) | 單向唯讀資料流、`IndexedDB` (`FileSystemFileHandle`) + `localStorage` 雙層持久化、跨主題 Storage Schema 表、雙向編輯寫回 (`createWritable`) 備案 |
| **調整畫布版面、2x 節點物理間距、實線／虛線關聯邏輯、PRTS 菱形節點或封面預覽 UX** | [**`ADR-003-hero-canvas-and-bidirectional-edges.md`**](file:///m:/Github/ArkPlots-Graph/docs/adr/ADR-003-hero-canvas-and-bidirectional-edges.md) | 頂部滿版畫布＋下方四欄設定、2 倍物理間距參數 (`9200/d2`, `L0=145`)、羅德島青實線前置 (`ancestors`) ＋ 源石琥珀虛線下一層 (`directSuccessors`)、右側懸浮檔案卡 `#selCard` |

---

## 📚 文件清單

1. **[ADR-001：同級並排獨立 Repo、零污染隔離與 `v1` 多主題版本分層架構](file:///m:/Github/ArkPlots-Graph/docs/adr/ADR-001-arkplots-graph-architecture.md)** (`Accepted - v1`)
2. **[ADR-002：單向資料流、雙層持久化記憶 (`IndexedDB` + `localStorage`) 與雙向寫回備案](file:///m:/Github/ArkPlots-Graph/docs/adr/ADR-002-persistence-and-data-flow.md)** (`Accepted - v1`)
3. **[ADR-003：主圖優先版面、2x 物理間距調校、雙向拓撲關聯線與 PRTS 視覺 UX](file:///m:/Github/ArkPlots-Graph/docs/adr/ADR-003-hero-canvas-and-bidirectional-edges.md)** (`Accepted - v1`)
4. **[AI-MAINTENANCE-GUIDE：AI 維護速查手冊（行號熱區、資料型別、函式索引表與呼叫圖）](file:///m:/Github/ArkPlots-Graph/docs/adr/AI-MAINTENANCE-GUIDE.md)** (`Living Reference - v1`)
