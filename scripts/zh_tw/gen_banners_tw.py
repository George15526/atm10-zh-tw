#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# atm10-zh-tw — All the Mods 10 繁體中文（台灣）版
# SPDX-License-Identifier: GPL-3.0-or-later
"""任務書章節橫幅（約 200 張，字烤在 PNG 裡）的繁體版。

**不改上游的 scripts/gen_quest_banners.py**，而是載入它之後換掉四樣東西：

- `BANNERS`：圖 → 文字。上游的值是簡體章節標題，這裡用同一個轉換器轉成繁體，
  所以橫幅、任務書側欄、章節標題三處的繁體字逐字一致；
- `FONTS_DIR` / `PIXEL_CHARSET`：換成繁體（台灣字形）字型——Noto Sans TC / Noto Serif TC、
  縫合像素字型的 zh_hant 版，字重與上游的 SC 版一一對應；
- `OUT`：寫到 build/zh_tw/questpics/，由 build_tw.py --banners 換進資源包。

版面（擦除框、取色、像素倍率、材質板）全部沿用上游，上游調了哪張圖，這裡自動跟上。
原圖來自整合包本體（ATM_PACK_ROOT，或 fetch_pack.py --no-jars 取的 overrides）。

用法:
    ATM_PACK_ROOT=build/packsrc/8.1 python3 scripts/zh_tw/gen_banners_tw.py
"""
import importlib
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'scripts'))

import fetch_fonts_tw  # noqa: E402
from build_tw import load_vanilla  # noqa: E402
from converter import Converter, build_name_dict, load_terms  # noqa: E402

OUT = ROOT / 'build' / 'zh_tw' / 'questpics'


def applicable(banners, src, titles):
    """→ (這一版要畫的, 跳過的)。

    上游的 BANNERS 跟著最新版走（8.3 新增「機械動力附屬」章的 create/caddon_*），
    繁體版對著較舊的版本重繪時，那幾張原圖本來就不存在。只跳過「原圖不在、
    章節檔也沒引用」的——章節引用了卻找不到原圖，照樣留給上游的 main() 報紅。
    原圖目錄或章節檔整個取不到時直接紅，不然會把全部橫幅當成「這版沒有」跳過。
    """
    if not src.is_dir():
        sys.exit('❌ 找不到原圖目錄 %s' % src)
    if not titles:
        sys.exit('❌ 章節檔裡找不到任何橫幅引用，ATM_PACK_ROOT 多半指錯了')
    keep, skip = {}, []
    for rel, text in banners.items():
        if (src / rel).exists() or rel in titles:
            keep[rel] = text
        else:
            skip.append(rel)
    return keep, sorted(skip)


def main():
    if not os.environ.get('ATM_PACK_ROOT'):
        sys.exit('❌ 請設 ATM_PACK_ROOT 指向整合包（或 fetch_pack.py --no-jars 取的目錄）')
    fonts = fetch_fonts_tw.ensure()          # 缺字型或雜湊不符直接失敗
    gqb = importlib.import_module('gen_quest_banners')

    terms, post, exclude, rules = load_terms()
    conv = Converter(terms, post, rules=rules)
    conv.set_name_dict(build_name_dict(conv, *load_vanilla(), exclude))

    gqb.FONTS_DIR = fonts
    gqb.PIXEL_CHARSET = {s: gqb.ttf_charset(gqb.pixel_face(s))
                         for s in gqb.PIXEL_SIZES if gqb.pixel_face(s)}
    if set(gqb.PIXEL_CHARSET) != set(gqb.PIXEL_SIZES):
        sys.exit('❌ 繁體像素字型不全：%s' % sorted(gqb.PIXEL_CHARSET))
    banners, skip = applicable(gqb.BANNERS, gqb.SRC, gqb.chapter_titles())
    for rel in skip:
        print('  略過 %s（這一版沒有這張圖，章節也沒引用）' % rel)
    gqb.BANNERS = {rel: conv.convert(text) for rel, text in banners.items()}
    gqb.OUT = OUT
    gqb.main()


if __name__ == '__main__':
    main()
