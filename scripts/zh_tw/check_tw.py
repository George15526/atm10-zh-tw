#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# atm10-zh-tw — All the Mods 10 繁體中文（台灣）版
# SPDX-License-Identifier: GPL-3.0-or-later
"""繁體出貨包的閘門。

1. **殘留簡體字**：拆開 zh_tw 包逐檔掃描。判定「簡體字」的依據是
   「OpenCC s2tw 會改它」**而且**「原版官方 zh_tw 裡從沒出現過它」——
   台、岩、群、床這類兩岸通用字在原版繁中裡出現過，不會被誤判。
   刻意保留簡體的地方（奖杯的簡體鍵、資源蜂腳本的 PB_SYS / PB_ZH_ALIAS 鍵）不計。
   授權文件（LICENSE*）與更新紀錄不屬於遊戲內文字，只報不擋。
2. **骨架不變**（--against <簡體 zip>）：把每個檔案的中日韓字元全部拿掉之後，
   簡繁兩版必須逐字相同。這保證色碼（&#RRGGBB、§、&）、佔位符（%s、$()）、跳脫、
   換行與 JSON/SNBT 結構一個位元組都沒被轉換動到。OpenCC 詞庫裡有中英混寫的詞
   （B超、U盘…）會吃掉色碼裡的字母，這道檢查就是為它設的。
   刻意改動的檔案（安裝器、更新連結、pack.mcmeta…）列在 SKELETON_EXEMPT。
3. **詞表核對**（--terms）：每條詞表在原版 cn ↔ tw 對照中的一致率，
   低於門檻的列出來給人看（不擋——有些詞是刻意偏離原版的，見 terms.json 的說明）。

取不到原版 zh_tw 時直接失敗（判據取不到就不能放行）。

用法:
    python3 scripts/zh_tw/check_tw.py dist/atm10-zh_tw-*.zip
    python3 scripts/zh_tw/check_tw.py --terms
"""
import argparse
import io
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0]))

import opencc  # noqa: E402
import vanilla  # noqa: E402
from converter import load_terms  # noqa: E402

HAN = re.compile('[一-鿿]')
TEXT_EXT = ('.json', '.snbt', '.md', '.txt', '.js', '.mcmeta', '.url', '.sh', '.ps1',
            '.gui', '.mdx', '.toml', '.cfg')
INFO_ONLY = re.compile(r'(^|/)(LICENSE[^/]*|CHANGELOG\.md|THIRD-PARTY-LICENSES\.md)$|(^|/)licenses/')
PB_LINE = re.compile(r'^const (PB_SYS|PB_ZH_ALIAS) = ')


def _vanilla(name):
    try:
        return json.loads(vanilla.asset_object('/nonexistent', name).decode('utf-8-sig'))
    except Exception as e:  # noqa: BLE001
        sys.exit(f'❌ 取不到原版 {name}，無法判定簡體字：{e}')


def simplified_detector():
    tw = _vanilla('minecraft/lang/zh_tw.json')
    legit = set(HAN.findall(''.join(tw.values())))
    s2tw = opencc.OpenCC('s2tw')
    cache = {}

    def is_simp(ch):
        r = cache.get(ch)
        if r is None:
            r = cache[ch] = ch not in legit and s2tw.convert(ch) != ch
        return r
    return is_simp


def _allow_words():
    data = json.loads((HERE.parents[1] / 'src' / 'zh_tw' / 'terms.json').read_text(encoding='utf-8'))
    words = sorted(data.get('check_allow_words', {}).get('words', []), key=len, reverse=True)
    return re.compile('|'.join(map(re.escape, words))) if words else None


ALLOW = _allow_words()


def _strip_intentional(rel, text):
    text = _strip_intentional_0(rel, text)
    return ALLOW.sub('', text) if ALLOW else text


def _strip_intentional_0(rel, text):
    if re.search(r'/lang/[^/]+\.json$', rel):
        # 語言檔只看值：鍵不會顯示給玩家；奖杯的簡體鍵還是刻意保留的（舊存檔裡已烘焙的名字）
        return '\n'.join(v for v in json.loads(text).values() if isinstance(v, str))
    if '/kubejs/' in rel and rel.endswith('.js'):
        return '\n'.join(l for l in text.splitlines() if not PB_LINE.match(l))
    return text


def iter_texts(zpath):
    with zipfile.ZipFile(zpath) as z:
        for n in z.namelist():
            if n.endswith('.zip'):
                with zipfile.ZipFile(io.BytesIO(z.read(n))) as inner:
                    for m in inner.namelist():
                        if m.endswith(TEXT_EXT):
                            yield f'{n}!/{m}', inner.read(m)
            elif n.endswith(TEXT_EXT):
                yield n, z.read(n)


def check_zip(zpath, is_simp):
    bad, info = Counter(), Counter()
    samples = {}
    for rel, raw in iter_texts(zpath):
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            continue
        text = _strip_intentional(rel, text)
        hits = [c for c in HAN.findall(text) if is_simp(c)]
        if not hits:
            continue
        (info if INFO_ONLY.search(rel) else bad)[rel] += len(hits)
        if rel not in samples:
            c = hits[0]
            i = text.index(c)
            samples[rel] = text[max(0, i - 15):i + 15].replace('\n', ' ')
    return bad, info, samples


SKELETON_EXEMPT = re.compile(
    r'(^|/)(install\.(sh|ps1)|[^/]*\.url|請安裝前務必看我\.md|pack\.mcmeta)$'
    r'|(^|/)config/vaultpatcher_asm/config\.json$'
    r'|(^|/)config/fancymenu/customization/title_screen_layout\.txt$'
    r'|(^|/)kubejs/client_scripts/hanhua_(pack|update)_check\.js$'
    r'|(^|/)kubejs/(client|server)_scripts/pb_hanhua_[^/]*\.js$')
# \u5f15\u865f\u4e5f\u4e00\u4f75\u62ff\u6389\uff1a\u201c\u2026\u201d \u2192 \u300c\u2026\u300d \u662f\u523b\u610f\u7684\uff08converter.taiwan_quotes\uff09\uff0c\u4e0d\u662f\u9aa8\u67b6\u88ab\u52d5\u5230
CJK_ALL = re.compile('[\u3400-\u9fff\uf900-\ufaff\U00020000-\U0003134f\u201c\u201d\u2018\u2019\u300c\u300d\u300e\u300f]')


def _flat(zpath):
    """{ 去掉頂層資料夾的路徑（zh_cn→zh_tw 正規化前）: bytes }，資源包 zip 攤開"""
    out = {}
    for rel, raw in iter_texts(zpath):
        rel = rel.split('/', 1)[1]
        rel = re.sub(r'resourcepacks/[^/]*\.zip!/', 'RP/', rel)
        out[rel] = raw
    return out


def check_skeleton(cn_zip, tw_zip, renames):
    def norm(rel):
        rel = rel.replace('zh_cn', 'zh_tw')
        for a, b in renames.items():
            rel = rel.replace(a, b)
        return rel
    cn = {norm(k): v for k, v in _flat(cn_zip).items()}
    tw = _flat(tw_zip)
    problems = []
    if set(cn) - set(tw):
        problems.append(f'繁體包少了檔案：{sorted(set(cn) - set(tw))[:5]}')
    for rel, a in cn.items():
        b = tw.get(rel)
        if b is None or SKELETON_EXEMPT.search(rel):
            continue
        a, b = a.decode('utf-8-sig', 'replace'), b.decode('utf-8-sig', 'replace')
        if re.search(r'/lang/zh_tw\.json$', rel):
            A, B = json.loads(a), json.loads(b)
            for k, v in A.items():
                if not isinstance(v, str):
                    continue
                if k not in B:
                    problems.append(f'{rel}：少了鍵 {k}')
                    continue
                # 原版官方譯名會帶空格（TNT矿车 → TNT 礦車），只容許空格差異
                if CJK_ALL.sub('', v).replace(' ', '') != CJK_ALL.sub('', B[k]).replace(' ', ''):
                    problems.append(f'{rel}：{k}：{v[:40]!r} → {B[k][:40]!r}')
            continue
        if CJK_ALL.sub('', a) != CJK_ALL.sub('', b):
            la, lb = CJK_ALL.sub('', a).splitlines(), CJK_ALL.sub('', b).splitlines()
            i = next((i for i, (x, y) in enumerate(zip(la, lb)) if x != y), min(len(la), len(lb)))
            problems.append(f'{rel} 第 {i + 1} 行：{a.splitlines()[i][:80]!r} → {b.splitlines()[i][:80]!r}'
                            if i < min(len(la), len(lb)) else f'{rel}：行數不同')
    return problems


def check_terms():
    cn = _vanilla('minecraft/lang/zh_cn.json')
    tw = _vanilla('minecraft/lang/zh_tw.json')
    terms, *_ = load_terms()
    weak = []
    longer = {a: [x for x in terms if a in x and x != a] for a in terms}

    def bare(a, v):
        # 這個詞在 v 裡至少有一處不屬於更長的詞條（更長的詞條會先命中，輪不到它）
        for x in longer[a]:
            v = v.replace(x, '\0')
        return a in v

    for a, b in terms.items():
        ks = [k for k, v in cn.items() if k in tw and bare(a, v)]
        if not ks:
            continue
        ok = sum(1 for k in ks if b in tw[k])
        if ok / len(ks) < 0.6:
            weak.append((ok, len(ks), a, b))
    for ok, n, a, b in sorted(weak):
        print(f'  {a} → {b}：原版 {n} 條含「{a}」，對應繁中含「{b}」的只有 {ok} 條')
    print(f'詞表 {len(terms)} 條，一致率偏低 {len(weak)} 條（僅供人工複核）')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('zips', nargs='*', type=Path)
    ap.add_argument('--terms', action='store_true')
    ap.add_argument('--against', type=Path, nargs='+', default=[],
                    help='對應的簡體 zip（依 client/server 配對），做骨架不變檢查')
    ap.add_argument('--show', type=int, default=20)
    args = ap.parse_args()
    if args.terms:
        check_terms()
    if not args.zips:
        return
    is_simp = simplified_detector()
    failed = False
    for z in args.zips:
        bad, info, samples = check_zip(z, is_simp)
        print(f'── {z.name}：殘留簡體字 {sum(bad.values())} 處／{len(bad)} 檔'
              f'（授權與更新紀錄另有 {sum(info.values())} 處，不擋）')
        for rel, n in bad.most_common(args.show):
            print(f'   {n:6d}  {rel}   …{samples[rel]}…')
        failed |= bool(bad)
        side = '-client-' if '-client-' in z.name else '-server-'
        for cz in [c for c in args.against if side in c.name]:
            cfg = json.loads((HERE.parents[1] / 'src' / 'zh_tw' / 'config.json').read_text(encoding='utf-8'))
            renames = {k: v for k, v in cfg['renames'].items() if not k.startswith('_')}
            probs = check_skeleton(cz, z, renames)
            print(f'   骨架對照 {cz.name}：{len(probs)} 處不一致')
            for p in probs[:args.show]:
                print('     ' + p)
            failed |= bool(probs)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
