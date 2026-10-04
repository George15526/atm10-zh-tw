# 繁體中文（台灣）版：開發說明

本倉庫 fork 自 [chiba233/atm10-zh-cn](https://github.com/chiba233/atm10-zh-cn)（簡體版），
另外出一套**繁體中文（台灣）**包。

## 原則：簡體仍是唯一真源

繁體**不在 `src/` 裡另存一份**，而是在出包時由簡體 zip 現轉：

```
上游簡體管線（完全不改）           繁體層（只有本 fork 有）
src/ → build/ → dist/atm10-zh_cn-*.zip ──► scripts/zh_tw/build_tw.py ──► dist/atm10-zh_tw-*.zip
                                              ▲
                              src/zh_tw/terms.json、overrides.json、config.json
```

所以合併上游時，衝突面只有本 fork 新增的檔案：

| 路徑 | 用途 |
|---|---|
| `scripts/zh_tw/converter.py` | 簡 → 繁轉換核心 |
| `scripts/zh_tw/build_tw.py` | zh_cn zip → zh_tw zip |
| `scripts/zh_tw/check_tw.py` | 閘門：殘留簡體字、骨架不變、詞表核對 |
| `scripts/zh_tw/test_zh_tw.py` | 閘門與轉換的反例測試 |
| `scripts/zh_tw/images_tw.py` | 重繪主選單按鈕上的字 |
| `scripts/zh_tw/gen_banners_tw.py` | 任務書章節橫幅：載入上游 gen_quest_banners.py，換成繁體文字與字型 |
| `scripts/zh_tw/fetch_fonts_tw.py` | 取五個繁體（台灣字形）字型並核雜湊 |
| `src/zh_tw/terms.json` | 台灣用語詞表、上下文規則、放行詞 |
| `src/zh_tw/overrides.json` | 逐鍵人工覆寫（優先於一切） |
| `src/zh_tw/config.json` | 本倉庫網址、中文檔名對照、語言定義、按鈕文字、字型 |
| `src/zh_tw/package/README.{client,server}.md` | 包內「請安裝前務必看我.md」（繁體版自己的說明，不轉換上游那份） |
| `.github/README.md` | GitHub 首頁說明（GitHub 優先顯示它；根目錄的 README.md 是上游的，不動以免合併衝突） |
| `requirements-zh_tw.lock` | OpenCC（釘版本與雜湊） |
| `.github/workflows/zh_tw.yml` | 由上游 release 轉出繁體包 |

## 同步上游

```bash
git remote add upstream https://github.com/chiba233/atm10-zh-cn.git   # 只需一次
git fetch upstream && git merge upstream/main
```

上游發新版後，Actions → `zh_tw` → 填上游 tag（例 `vr27`）即可產出繁體包。
本地也可以：

```bash
python -m pip install --require-hashes -r requirements-zh_tw.lock -r requirements.lock
python scripts/zh_tw/fetch_fonts_tw.py
gh release download vr26 -R chiba233/atm10-zh-cn -p 'atm10-zh_cn-*.zip' -D upstream
python scripts/fetch_pack.py 8.1 build/packsrc/8.1 --no-jars          # 橫幅原圖
ATM_PACK_ROOT=build/packsrc/8.1 python scripts/zh_tw/gen_banners_tw.py   # → build/zh_tw/questpics/
python scripts/zh_tw/build_tw.py upstream/atm10-zh_cn-*.zip --out dist --banners build/zh_tw/questpics [--mods <整合包>/mods]
python scripts/zh_tw/check_tw.py dist/atm10-zh_tw-*.zip --against upstream/atm10-zh_cn-*.zip
```

自己從原始碼構建簡體時（`scripts/build_dist.sh`），把它的產物 `dist/atm10-zh_cn-*.zip` 餵給 `build_tw.py` 即可。

## 轉換順序

每段文字依序套用（命中處以佔位符保護，後面的步驟不會再改它）：

1. **名稱字典**：原版官方整條名稱（远古残骸 → 遠古遺骸）。本身又是其他名稱一部分的（深色橡木）不收。
2. **上下文規則**（`terms.json` 的 `regex_rules`）：凋灵／恶魂 單獨成詞 → 凋零怪／地獄幽靈、
   粗X → X原礦、深层X矿石 → 深板岩X礦石、X后 → X後…
3. **詞表**（`terms.json` 的 `groups`）：最長優先。
4. **OpenCC s2twp**：只吃**非 ASCII 片段**——它的詞庫有中英混寫的詞（B超、U盘），
   會吃掉色碼 `&#4497DB` 的字母。
5. **字形統一**（`post_chars`）：臺 → 台、箇 → 個。
6. **引號**：中文語境裡成對的 “…” ‘…’ → 「…」 『…』（`converter.taiwan_quotes`）；英文撇號與不成對的引號不動。

語言檔另外有兩層更優先的：`overrides.json` 的逐鍵覆寫，以及「值與原版 zh_cn 相同的原版鍵直接取官方 zh_tw」。

## 用語的依據

- **原版名詞**：一律照 Minecraft 原版官方 zh_tw（終界、地獄、獄髓、半磚、階梯、生怪磚…）。
  `check_tw.py --terms` 會逐條核對詞表與原版的一致率。
- **原版沒有的詞**：取 ATM10 全部模組自帶 zh_tw 的多數用法，數字寫在 `terms.json` 各組的 `_why`
  （高級 109／高階 8、類型 86／型別 0、插件 26／外掛 0…）。
- 儲存方塊（Block of Osmium 這類）照 OpenCC 的「塊」：模組自帶 zh_tw 裡「塊」49、「方塊」32，沒有定論，不硬推。

## 新增或修正譯名

- **某個詞整體都要改** → 加進 `terms.json` 的 `groups`。先用 `python scripts/zh_tw/converter.py '<簡體句子>'` 試。
- **要看上下文** → `regex_rules`（`\1` 代表第 1 組，單獨做 OpenCC）。
- **只改某一條** → `overrides.json` 的 `lang.<命名空間>.<鍵>`，並在 `_notes` 寫出處。
- **閘門誤報**（台灣也這樣寫的詞，如 傢伙、干涉、皇后）→ `check_allow_words`，只收整個詞。

改完一定要重跑：

```bash
python scripts/zh_tw/test_zh_tw.py
python scripts/zh_tw/build_tw.py upstream/*.zip --out dist
python scripts/zh_tw/check_tw.py dist/atm10-zh_tw-*.zip --against upstream/atm10-zh_cn-*.zip
```

## 特別處理過的地方（上游改了這些檔案，build_tw.py 會直接報錯）

| 檔案 | 處理 |
|---|---|
| `install.sh` / `install.ps1` | `zh_cn` → `zh_tw`（路徑、`lang:`）、更新查詢改查本倉庫 |
| `hanhua_update_check.js`、主選單按鈕、`.url` | 連結改到本倉庫 |
| `hanhua_pack_check.js` | 自檢的語言檔路徑改 `lang/zh_tw.json` |
| `pb_hanhua_*.js` 的 `PB_SYS` / `PB_ZH_ALIAS` | 鍵保留簡體＋加繁體（簡體版時期烘焙進存檔的蜂名仍要認得） |
| `hanhua_trophies` 語言檔 | 鍵是烘焙進物品的「實體名 + Trophy」，簡體鍵保留，另加與繁體實體名逐字一致的鍵 |
| `pack.mcmeta` | 語言定義改 zh_tw |
| `assets/*/font/` | 字形表，不轉 |

## 尚未完成

- **圖片裡的字**：主選單按鈕 18 張、任務書橫幅 202 張已重繪成繁體。仍是簡體的：MineColonies 速查手冊標題圖
  （上游 `gen_mod_textures.py` 產的）、AE2 系導覽書裡的介面截圖。
- 橫幅原圖要整合包本體：`fetch_pack.py --no-jars` 在部分網路環境會被 CurseForge 擋（403），
  這時把 `ATM_PACK_ROOT` 指向本機已安裝的 ATM10 實例即可（只讀不寫）。
- **模組自帶 zh_cn 的補位**（`--mods`，2026-10-01 決定開啟，CI 預設開）：Minecraft 的 zh_tw 不會回退到 zh_cn，
  簡體版沒覆蓋、靠模組自帶 zh_cn 顯示的內容到繁體會變英文。8.1 實測補上語言鍵約 1.48 萬條、導覽書 656 檔；
  模組自己有 zh_tw 的不補。補位內容是模組作者譯文的轉換版。
- **Tombstone 卷軸、XNet 手冊的 `-zh_cn.txt`** 已照樣改名為 `-zh_tw.txt`，讀取機制未實機驗證。
- **伺服器同時有簡繁玩家**：伺服器包只帶 zh_tw 任務書語言檔。
- 尚未實機進遊戲驗證。
