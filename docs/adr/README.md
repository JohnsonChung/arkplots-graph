# ArkPlots-Graph 架構決策紀錄 (ADR) 與 AI 維護索引

本目錄採用模組化拆分，將**「為什麼這樣設計（ADR 001～003）」**與**「程式碼怎麼改（AI 維護速查手冊）」**分離，讓後續 AI Agent 與開發者能依任務需求只讀取對應的單一檔案，最大化節省 Context Token 與瀏覽時間。

---

## 🧭 AI Agent 任務導航表（依任務挑選單一檔案閱讀）

| 當你的任務是…… | 請優先閱讀哪一份文件 | 內容摘要 |
| --- | --- | --- |
| **定位某個 Function 行號、查資料型別、查 DOM ID 或修改程式碼** | 👉 [**`AI-MAINTENANCE-GUIDE.md`**](file:///m:/Github/ArkPlots-Graph/docs/adr/AI-MAINTENANCE-GUIDE.md) | `index.html` 9 大行號熱區、13 個核心型別 (`classDiagram`)、41 個 JS 函式與 14 個 Python 函式速查表、呼叫管線圖 (`flowchart TD`)、DOM ID 對照表 |
| **了解獨立 Repo 結構、上游零污染規範、跨目錄封面路徑或主題分支** | [**`ADR-001-arkplots-graph-architecture.md`**](file:///m:/Github/ArkPlots-Graph/docs/adr/ADR-001-arkplots-graph-architecture.md) | 同級並排 Repo (`M:\Github\ArkPlots-Graph`)、單一入口 `index.html`、`user_data/` 隔離、`getCoverCandidates()` 跨目錄封面解析 |
| **修改 `Read_record.json` 綁定、記憶路徑、快取或擴充「雙向寫回」功能** | [**`ADR-002-persistence-and-data-flow.md`**](file:///m:/Github/ArkPlots-Graph/docs/adr/ADR-002-persistence-and-data-flow.md) | 單向唯讀資料流、`IndexedDB` (`FileSystemFileHandle`) + `localStorage` 雙層持久化、Storage Schema 表、雙向編輯寫回 (`createWritable`) 備案 |
| **調整畫布版面、實線／虛線關聯邏輯、右側懸浮窗 `#selCard` 或 Hover 封面 `#tip`** | [**`ADR-003-hero-canvas-and-bidirectional-edges.md`**](file:///m:/Github/ArkPlots-Graph/docs/adr/ADR-003-hero-canvas-and-bidirectional-edges.md) | 頂部滿版畫布＋下方四欄設定、實線必要前置 (`ancestors`) ＋ 琥珀金虛線下一層 (`directSuccessors`)、右側懸浮窗與 Hover 防閃爍封面預覽 |

---

## 📚 文件清單

1. **[ADR-001：同級並排獨立 Repo、零污染隔離與單一入口架構](file:///m:/Github/ArkPlots-Graph/docs/adr/ADR-001-arkplots-graph-architecture.md)** (`Accepted`)
2. **[ADR-002：單向資料流、雙層持久化記憶 (`IndexedDB` + `localStorage`) 與雙向寫回備案](file:///m:/Github/ArkPlots-Graph/docs/adr/ADR-002-persistence-and-data-flow.md)** (`Accepted`)
3. **[ADR-003：主圖優先版面、雙向拓撲關聯線（實線前置＋虛線下一層）與封面預覽 UX](file:///m:/Github/ArkPlots-Graph/docs/adr/ADR-003-hero-canvas-and-bidirectional-edges.md)** (`Accepted`)
4. **[AI-MAINTENANCE-GUIDE：AI 維護速查手冊（行號熱區、資料型別、函式索引表與呼叫圖）](file:///m:/Github/ArkPlots-Graph/docs/adr/AI-MAINTENANCE-GUIDE.md)** (`Living Reference`)
