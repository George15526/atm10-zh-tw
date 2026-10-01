#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# atm10-zh-tw — All the Mods 10 繁體中文（台灣）版
# SPDX-License-Identifier: GPL-3.0-or-later
"""取繁體圖片重繪用的字型，逐個核 sha256。

與上游 scripts/fetch_fonts.sh 的五個字型一一對應，只換成台灣字形：

    bold      Noto Sans TC Bold      （上游 Noto Sans SC Bold）
    thin      Noto Sans TC Light     （上游 Noto Sans SC Light）
    serif     Noto Serif TC Black    （上游 Noto Serif SC Black）
    pixel-10  縫合像素字型 10px zh_hant（上游 zh_hans）
    pixel-12  縫合像素字型 12px zh_hant

全部 OFL-1.1（授權全文：assets-src/fonts/noto-OFL.txt、pixel-OFL.txt）。
下載網址與雜湊在 src/zh_tw/config.json 的 fonts_tc；字型一換版圖就會變，所以雜湊不符一律失敗。
放在 assets-src/fonts/tc/（.gitignore 已排除 assets-src/fonts/*）。

用法:
    python3 scripts/zh_tw/fetch_fonts_tw.py
"""
import hashlib
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'assets-src' / 'fonts' / 'tc'


def spec():
    cfg = json.loads((ROOT / 'src' / 'zh_tw' / 'config.json').read_text(encoding='utf-8'))
    return {k: v for k, v in cfg['fonts_tc'].items() if not k.startswith('_')}


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'atm10-zh-tw'})
    last = None
    for _ in range(5):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return r.read()
        except OSError as e:   # noqa: PERF203
            last = e
    raise SystemExit(f'❌ 下載失敗 {url}：{last}')


def ensure(fetch=True):
    """回傳字型目錄；缺檔就下載（fetch=False 時直接失敗），雜湊不符一律失敗。"""
    DEST.mkdir(parents=True, exist_ok=True)
    for name, s in spec().items():
        p = DEST / s['file']
        if p.exists() and _sha(p.read_bytes()) == s['sha256']:
            continue
        if not fetch:
            sys.exit(f'❌ 缺字型 {p}（或雜湊不符）——先跑 scripts/zh_tw/fetch_fonts_tw.py')
        print(f'  下載 {name} …')
        data = _get(s['url'])
        if 'member' in s:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                data = z.read(s['member'])
        if _sha(data) != s['sha256']:
            sys.exit(f'❌ {name} 雜湊不符：{_sha(data)}（預期 {s["sha256"]}）')
        p.write_bytes(data)
    return DEST


if __name__ == '__main__':
    print(f'✅ 字型齊全：{ensure()}')
