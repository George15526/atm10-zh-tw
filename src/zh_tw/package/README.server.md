# ATM10 @@MCVER@@ 繁體中文（台灣）漢化包 · 伺服器端

> **單人玩家不需要本包**，裝客戶端包就夠了。本包是給開**專用伺服器**的人用的。

| 項目 | 版本 |
|---|---|
| 整合包 | All the Mods 10 **v@@MCVER@@** 專用伺服器 |
| Minecraft | 1.21.1 |
| 載入器 | NeoForge @@NEOFORGE@@ |

**必須與整合包版本嚴格對應，不能跨版本用。** 伺服器上每個玩家也要各自安裝對應版本的客戶端包。

## 安裝

1. **關閉伺服器**，並**備份**伺服器資料夾裡的 `config/`、`kubejs/`、`vaultpatcher/`、`mods/vaultpatcher.jar`（本包沒有自動安裝器）。
2. 把包內的 `mods/` `vaultpatcher/` `kubejs/` `config/` **覆蓋**到伺服器資料夾（含 `mods/`、`server.properties` 的那一層）。
   原本裝過簡體伺服器包的，直接覆蓋即可。
3. **完整重新啟動伺服器。**

只改了任務書文字時可以不重啟，在伺服器控制台執行 `ftbquests reload` 即可；VaultPatcher 與 KubeJS 的改動仍需完整重啟。

## 驗證

- 伺服器能正常啟動、`logs/latest.log` 沒有 KubeJS 或 VaultPatcher 的錯誤。
- 進服後：任務書標題／描述是繁體；進服公告是繁體；放進背包的蜂籠名稱是繁體。

## 注意

- 伺服器送出的文字（進服公告、部分機器提示、蜂籠名稱）對**所有玩家**都是繁體。
  用簡體客戶端的玩家也能正常遊玩，任務書與物品名照各自的語言顯示。
- 蜂籠名稱會被寫進存檔。之後若改回簡體伺服器包，已改成繁體的蜂籠名稱不會自動改回（只影響顯示）。
- ⚠️ **別把客戶端包的 `config/mysticalcustomization` 放到伺服器**——所有玩家進服會出現
  `error creating crop with id null`。本包不含該目錄。
- ⚠️ **別把客戶端的 VaultPatcher 模組放到伺服器**——會汙染物品資料與註冊名，損壞存檔。本包只含伺服器安全的模組。

## 回報問題與授權

問題回報：https://github.com/@@REPO@@/issues

本包由簡體中文「ATM10 漢化補丁·綠油油版」（星野夢華，https://github.com/chiba233/atm10-zh-cn ）轉換而來。
譯文內容依 CC BY-NC-SA 4.0 授權，程式碼依 GPL-3.0-or-later；授權全文見同目錄的 LICENSE。
