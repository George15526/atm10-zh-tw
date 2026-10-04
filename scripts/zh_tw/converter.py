#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# atm10-zh-tw — All the Mods 10 繁體中文（台灣）版
# SPDX-License-Identifier: GPL-3.0-or-later
"""簡體 → 繁體（台灣）轉換核心。

簡體仍是唯一真源（與上游 chiba233/atm10-zh-cn 同步）；繁體一律在構建時由這裡現轉，
不在 src/ 裡另存一份繁體副本——否則每次合併上游都要手動對兩份。

轉換分三層，優先序由高到低：

1. **逐鍵覆寫**（src/zh_tw/overrides.json）：人工校過的單條譯文，只作用於語言檔。
2. **原版官方譯名**：鍵存在於原版且我們的 zh_cn 值與原版 zh_cn 相同時，直接取原版 zh_tw。
3. **詞表 + 名稱字典 + OpenCC s2twp**：
   - 名稱字典：原版官方「整條名稱」cn → tw（如 金合欢木板 → 相思木材），
     讓正文裡提到的名稱與物品名完全一致；
   - 詞表（src/zh_tw/terms.json）：構詞成分（台阶 → 半磚、末地 → 終界…）；
   - 兩者在**簡體原文**上最長優先比對，命中處換成佔位符保護，剩下的交給 OpenCC，
     最後再把佔位符還原。這樣詞表結果不會被 OpenCC 二次改寫。
"""
import json
import re
import sys
from pathlib import Path

import opencc

ROOT = Path(__file__).resolve().parents[2]
SRC_TW = ROOT / 'src' / 'zh_tw'

# 佔位符用輔助私用區 A（U+F0000 起）。BMP 私用區（U+E000–F8FF）不能用：
# 不少模組把圖示字形放在那裡，原文裡本來就會出現。
_PUA_BASE = 0xF0000
_PUA_RE = re.compile('[\U000F0000-\U000FFFFD]')
# OpenCC 的 s2twp 詞庫裡有中英混寫的詞（B超→超音波、U盘→隨身碟…）。
# 「&#4497DB超频」會被吃掉色碼的 B，變成「&#4497D超音波頻」——色碼和字一起壞。
# 所以只把**非 ASCII 的連續片段**交給 OpenCC，ASCII 一個位元組都不讓它看到。
_NON_ASCII_RUN = re.compile('[^\x00-\x7f]+')
_CJK_RE = re.compile('[㐀-鿿豈-﫿]')


def load_terms(path=SRC_TW / 'terms.json'):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    terms = {}
    for group, entries in data['groups'].items():
        for cn, tw in entries.items():
            if cn.startswith('_'):
                continue
            if cn in terms:
                raise SystemExit(f'❌ terms.json：「{cn}」在多個分組裡重複（{group}）')
            terms[cn] = tw
    post = {k: v for k, v in data.get('post_chars', {}).items() if not k.startswith('_')}
    exclude = set(data.get('name_dict_exclude', {}).get('names', []))
    rules = [(r['pattern'], r['tw']) for r in data.get('regex_rules', {}).get('rules', [])]
    return terms, post, exclude, rules


class Converter:
    def __init__(self, terms=None, post_chars=None, name_dict=None, rules=()):
        if terms is None:
            terms, post_chars, _, rules = load_terms()
        # 需要看上下文才能定的詞（如「凋灵」單獨出現才是生物名「凋零怪」），
        # 在詞表之前先套，命中處同樣以佔位符保護
        self.rules = [(re.compile(p), tw) for p, tw in rules]
        self._cc = opencc.OpenCC('s2twp')
        self.terms = dict(terms)
        self.name_dict = dict(name_dict or {})
        self.post_chars = dict(post_chars or {})
        self._post_tbl = str.maketrans(self.post_chars)
        self._rebuild()

    def _rebuild(self):
        # 同一個字串兩邊都有時詞表優先：詞表收的是構詞成分（深色橡木 → 黑橡木），
        # 名稱字典收的是整條名稱（深色橡木 → 黑橡木塊）。當成詞套進正文時要的是前者。
        # 套用順序：名稱字典（原版整條名稱）→ 上下文規則 → 詞表。
        # 名稱字典最先，否則「粗铁块」會先被「粗X → X原礦」規則吃掉，得不到官方的「鐵原礦方塊」。
        nd = {k: v for k, v in self.name_dict.items() if k not in self.terms}
        self._nd = nd
        self._nd_re = re.compile('|'.join(map(re.escape, sorted(nd, key=len, reverse=True)))) if nd else None
        self._table = self.terms
        keys = sorted(self.terms, key=len, reverse=True)
        self._re = re.compile('|'.join(map(re.escape, keys))) if keys else None
        self._cache = {}

    def set_name_dict(self, name_dict):
        self.name_dict = dict(name_dict)
        self._rebuild()

    def convert(self, text):
        if not text or not _CJK_RE.search(text):
            return text
        hit = self._cache.get(text)
        if hit is not None:
            return hit
        if _PUA_RE.search(text):
            raise ValueError(f'原文含輔助私用區字元，佔位符會衝突：{text[:60]!r}')
        slots = []

        def protect(m):
            slots.append(self._table[m.group(0)])
            return chr(_PUA_BASE + len(slots) - 1)

        def protect_nd(m):
            slots.append(self._nd[m.group(0)])
            return chr(_PUA_BASE + len(slots) - 1)

        def rule(m, tw):
            # tw 裡的 \\1、\\2 換成對應分組的轉換結果（分組本身只做 OpenCC，不再套規則）
            out = re.sub(r'\\(\d)', lambda g: self._cc.convert(m.group(int(g.group(1))) or ''), tw)
            slots.append(out.translate(self._post_tbl))
            return chr(_PUA_BASE + len(slots) - 1)

        masked = self._nd_re.sub(protect_nd, text) if self._nd_re else text
        for pat, tw in self.rules:
            masked = pat.sub(lambda m, tw=tw: rule(m, tw), masked)
        masked = self._re.sub(protect, masked) if self._re else masked
        out = _NON_ASCII_RUN.sub(lambda m: self._cc.convert(m.group(0)), masked)
        out = out.translate(self._post_tbl)
        out = _PUA_RE.sub(lambda m: slots[ord(m.group(0)) - _PUA_BASE], out)
        out = taiwan_quotes(out)
        self._cache[text] = out
        return out


_HAN = '[㐀-鿿豈-﫿　-〿！-～]'   # 漢字與全形標點
_DQ = re.compile('“([^“”\n]*)”')
_SQ = re.compile('‘([^‘’\n]*)’')


def taiwan_quotes(s):
    """簡中習慣的 “…” ‘…’ → 台灣慣用的 「…」 『…』。

    只換成對的引號，且要確定是中文語境：
    - 雙引號：內容有中文，或緊鄰的前後字是中文（「%s」這種夾在中文句子裡的也算）；
    - 單引號：內容必須有中文——’ 同時是英文撇號（Explorer’s），不能憑鄰字判斷。
    不成對的（原文少打一邊）不動，免得配錯對。
    """
    if '“' not in s and '‘' not in s:
        return s

    def dq(m):
        before = s[m.start() - 1] if m.start() else ''
        after = s[m.end()] if m.end() < len(s) else ''
        if re.search(_HAN, m.group(1)) or re.match(_HAN, before) or re.match(_HAN, after):
            return '「' + m.group(1) + '」'
        return m.group(0)

    s = _DQ.sub(dq, s)
    return _SQ.sub(lambda m: '『' + m.group(1) + '』' if re.search(_HAN, m.group(1)) else m.group(0), s)


def build_name_dict(conv, vanilla_cn, vanilla_tw, exclude, extra=()):
    """原版官方整條名稱 cn → tw。

    只收「照詞表 + OpenCC 轉出來與官方不同」的名稱——相同的收了也沒用。
    少於 3 個字的不收：兩個字的名稱（凋灵、恶魂…）太容易是別的詞的一部分，
    交給詞表處理構詞成分即可，原版鍵本身仍照官方值出。
    本身又是別的原版名稱一部分的也不收（深色橡木 ⊂ 深色橡木木板）：它其實是構詞成分，
    整條名稱「黑橡木塊」套進「深色橡木窗户板」就成了「黑橡木塊窗戶板」。
    """
    prefixes = ('block.minecraft.', 'item.minecraft.', 'entity.minecraft.',
                'biome.minecraft.', 'effect.minecraft.', 'enchantment.minecraft.')
    names = {v for k, v in vanilla_cn.items()
             if k.startswith(prefixes) and k.count('.') == 2 and isinstance(v, str)}
    blob = '\n'.join(names)
    nd = {}
    for k, cn in vanilla_cn.items():
        if not k.startswith(prefixes) or k.count('.') != 2:
            continue
        if blob.count(cn) > 1 or any(cn in n and cn != n for n in names):
            continue
        tw = vanilla_tw.get(k)
        if not tw or len(cn) < 3 or cn in exclude or '%' in cn:
            continue
        if conv.convert(cn) != tw:
            nd.setdefault(cn, tw)
    for cn, tw in extra:
        if len(cn) >= 3 and cn not in exclude:
            nd.setdefault(cn, tw)
    return nd


if __name__ == '__main__':
    c = Converter()
    for line in sys.argv[1:] or [sys.stdin.read()]:
        print(c.convert(line))
