#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# atm10-zh-tw — All the Mods 10 繁體中文（台灣）版
# SPDX-License-Identifier: GPL-3.0-or-later
"""把簡體包裡「烤進 PNG 的中文」重繪成繁體。

主選單按鈕的字是畫在圖上的（FancyMenu 直接貼圖），語言設定管不到。
上游的 scripts/gen_menu_buttons.py 是「擦掉英文、寫中文」；這裡直接拿**簡體成品**當底稿：
擦除矩形是常數、矩形內只有字、矩形外是純色背景（見上游的說明），
所以擦掉簡體再寫繁體，結果與從英文原圖重繪完全相同，不需要整合包原圖。

版面常數（BOX / BASELINE_BOTTOM / CENTER_X / TARGET_H）抄自 gen_menu_buttons.py；
上游若改了版面，這裡的越界檢查會擋下來。

字型用 Noto Sans **TC** Bold（台灣字形），與上游的 Noto Sans SC Bold 同一家族同一粗細。
"""
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
CFG = json.loads((ROOT / 'src' / 'zh_tw' / 'config.json').read_text(encoding='utf-8'))

# ── 與 scripts/gen_menu_buttons.py 相同的版面常數 ──
BOX = (280, 50, 900, 143)
BASELINE_BOTTOM = 132
CENTER_X = 562
TARGET_H = 62
SS = 4

MENU_RE_DIR = 'config/fancymenu/assets/'


def menu_words():
    return {k: v for k, v in CFG['menu_buttons'].items() if not k.startswith('_')}


_FONT = None


def font_path():
    global _FONT
    if _FONT is None:
        import fetch_fonts_tw
        _FONT = str(fetch_fonts_tw.ensure(fetch=False) / 'bold.otf')   # 只核雜湊，不在出包時下載
    return _FONT


def _text_color(im):
    px = im.load()
    best, col = 10 ** 9, None
    for y in range(BOX[1], BOX[3] + 1):
        for x in range(BOX[0], BOX[2] + 1):
            r, g, b, a = px[x, y]
            if a > 200 and r + g + b < best:
                best, col = r + g + b, (r, g, b, 255)
    return col


def _render(word, color, target_h=TARGET_H):
    size = int(round(target_h / 0.86))
    for _ in range(8):
        f = ImageFont.truetype(font_path(), size * SS)
        tmp = Image.new('RGBA', (size * SS * (len(word) + 2), size * SS * 3), (0, 0, 0, 0))
        ImageDraw.Draw(tmp).text((size * SS, size * SS), word, font=f, fill=color)
        bb = tmp.getbbox()
        h = (bb[3] - bb[1]) / SS
        if abs(h - target_h) < 0.6:
            break
        size = max(1, int(round(size * target_h / h)))
    glyph = tmp.crop(bb)
    return glyph.resize((max(1, round(glyph.width / SS)), max(1, round(glyph.height / SS))),
                        Image.LANCZOS)


def redraw_menu_button(raw, rel):
    """rel 是 config/fancymenu/assets/<stem>_<color|gray>.png；不在對照表裡的回傳 None"""
    name = rel.rsplit('/', 1)[-1]
    stem = name.rsplit('_', 1)[0]
    word = menu_words().get(stem)
    if word is None:
        return None
    im = Image.open(io.BytesIO(raw)).convert('RGBA')
    if im.width <= 930 or im.height <= BOX[3]:
        sys.exit(f'❌ {rel}：尺寸 {im.size} 放不下擦除矩形 {BOX}，上游的按鈕版面可能改了')
    bg = im.getpixel((930, 60))
    col = _text_color(im)
    if col is None:
        sys.exit(f'❌ {rel}：擦除矩形裡找不到字，上游的按鈕版面可能改了')
    glyph = _render(word, col)
    x = int(round(CENTER_X - glyph.width / 2))
    y = BASELINE_BOTTOM - glyph.height + 1
    if x < BOX[0] or x + glyph.width > BOX[2] or y < BOX[1]:
        sys.exit(f'❌ {rel}：「{word}」越出擦除矩形 {BOX}')
    ImageDraw.Draw(im).rectangle(BOX, fill=bg)
    im.alpha_composite(glyph, (x, y))
    out = io.BytesIO()
    im.save(out, format='PNG', optimize=False, compress_level=9)
    return out.getvalue()
