# arkplots-graph `v1`

**明日方舟劇情關聯圖與閱讀進度視覺化工具**（羅德島 PRTS 戰術情報終端版）

![ArkPlots-Graph PRTS 預覽](docs/screenshots/preview-prts.png)

> **聲明**：本專案為**個人興趣製作**的純前端延伸視覺化小工具。《明日方舟》相關文本與圖像設定歸上海鷹角網路科技有限公司所有，僅供同好學習與整理閱讀進度交流使用。

---

## 🔗 與 `ArkPlots` 的使用關係

本工具是專為開源專案 **[`ApodidaeDeSwift/ArkPlots`](https://github.com/ApodidaeDeSwift/ArkPlots)** 設計的**外部單向視覺化與拓撲分析介面**：

1. **`ArkPlots`（上游資料與紀錄管理）**：負責維護完整的劇情資料庫 (`Plotline.json`)、活動封面圖庫 (`covers/`) 以及您在本地標記的個人閱讀進度 (`Read_record.json`)。
2. **`arkplots-graph`（本專案：全局關聯圖譜）**：
   - **零污染單向讀取**：直接讀取您在 `ArkPlots` 的資料夾或 `Read_record.json`，不修改上游任何原始碼或檔案。
   - **自動定位紀錄與封面圖**：點擊介面上的 **「📁 綁定 `ArkPlots` 資料夾 (含封面)」**（或直接把 `ArkPlots` 資料夾拖放進視窗），即可一次自動定位該目錄下的 `Read_record.json`、`Plotline.json` 與活動封面圖（支援安裝版 `_internal/web/dist/covers/` 與原始碼版 `web/dist/covers/`），**無須規定兩個資料夾的擺放位置**。
   - **雙向拓撲推演**：點擊圖上任一劇情節點（如 `068 孤星`），自動以**羅德島青實線 (`━━`)** 標示所有必讀前置鏈，並以**源石琥珀虛線 (`╌╌`)** 標示依賴該劇情的下一層後續作品。

---

## 🚀 快速使用

1. 下載並解壓縮 Release 的 **[`arkplots-graph-v1.zip`](https://github.com/JohnsonChung/arkplots-graph/releases/tag/v1)** 至任意位置，雙擊開啟 **[`index.html`](index.html)**（無須安裝任何環境或啟動伺服器）。
2. 在下方資料來源區（二選一）：
   - **推薦**：點擊 **「📁 綁定 `ArkPlots` 資料夾 (含封面)」** 並選擇您的 `ArkPlots` 安裝目錄（預設通常在 `%LOCALAPPDATA%\ArkPlots` 或您的自訂資料夾），即可自動載入閱讀進度與活動封面圖。
   - **僅讀紀錄**：點擊 **「📌 單選紀錄」** 單獨選取 `Read_record.json`（或直接將檔案／資料夾拖放進視窗）。
3. 瀏覽器會自動透過 `IndexedDB` 記住位置，後續在 `ArkPlots` 更新閱讀狀態後，可一鍵「🔄 重新同步」或勾選「⚡ 自動監聽存檔更新」。

---

## 🎨 主題版本說明

| 版本 | 檔案路徑 | 狀態與說明 |
| :--- | :--- | :--- |
| **`theme:PRTS`（預設版）** | [`index.html`](index.html) | **主力預設版本**。羅德島 PRTS 戰術終端風格，支援深色終端／淺色醫療檔案室切換。 |
| **`theme:終末地`** | [`themes/ArkPlots-Graph-endfield.html`](themes/ArkPlots-Graph-endfield.html) | **開發中預覽版本 (WIP)**。終末地重工與塔衛二工程藍圖風格。 |
| **`開發簡約版`** | [`themes/ArkPlots-Graph-dev.html`](themes/ArkPlots-Graph-dev.html) | **開發與除錯用版本**。保持最簡單的原生外觀，方便快速驗證資料與拓撲邏輯。 |
| `theme:liquid` / `retro` | [`themes/deprecated/`](themes/deprecated/) | **Deprecated（已棄用封存）**。早期視覺實驗版本，後續不再維護更新。 |
