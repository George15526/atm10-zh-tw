#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# atm10-zh-tw — All the Mods 10 繁體中文（台灣）版
# SPDX-License-Identifier: GPL-3.0-or-later
"""把簡體出貨包（zip）轉成繁體（台灣）出貨包。

    dist/atm10-zh_cn-client-r26-atm8.1.zip  →  dist/atm10-zh_tw-client-r26-atm8.1.zip
    dist/atm10-zh_cn-server-r26-atm8.1.zip  →  dist/atm10-zh_tw-server-r26-atm8.1.zip

## 為什麼在 zip 這一層轉

簡體版的整條管線（摊源、套上游補丁、生成器、閘門）完全不動，繁體只吃它的最終產物。
這樣合併上游時，衝突面只有 scripts/zh_tw/ 與 src/zh_tw/ 這兩個上游根本沒有的目錄；
上游改了哪個生成器，繁體版自動跟著吃到。也因此可以直接拿上游已發布的 zip 來轉。

## 做了哪些事

- 路徑：`zh_cn` → `zh_tw`（lang/zh_cn.json、_zh_cn/、patchouli 的 zh_cn/、
  任務書 lang/zh_cn/…）；中文檔名照 src/zh_tw/config.json 的 renames 表。
- 語言檔：逐鍵套 覆寫 → 原版官方 zh_tw → 詞表+名稱字典+OpenCC（見 converter.py）。
- 模組自帶 zh_cn 的補位（--mods）：Minecraft 的語言回退是 zh_tw → en_us，**不經過 zh_cn**。
  簡體版沒覆蓋、靠模組自帶 zh_cn 顯示的鍵，到繁體就會變回英文；給了 --mods 就把這些鍵
  轉成繁體補進資源包（模組自己有 zh_tw 的鍵不補，尊重模組作者的繁體譯文）。
- 其他文字檔（任務 snbt、導覽書、KubeJS、VaultPatcher、安裝器、說明文件）：整檔轉換，
  只動中日韓字元，換行與 BOM 原樣保留。
- 少數「中文同時是比對用的識別值」的地方特別處理（見 FIXUPS 與 _convert_pb_script）。

用法:
    python3 scripts/zh_tw/build_tw.py dist/atm10-zh_cn-*-r26-atm8.1.zip \\
        [--out dist] [--mods <整合包>/mods]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'scripts'))

import vanilla  # noqa: E402
from converter import Converter, build_name_dict, load_terms  # noqa: E402

SRC_TW = ROOT / 'src' / 'zh_tw'
CJK = re.compile('[㐀-鿿豈-﫿]')
CJK_ESCAPE = re.compile(r'\\u(?:[4-9][0-9a-fA-F]{3}|3[4-9a-fA-F][0-9a-fA-F]{2})')
LANG_RE = re.compile(r'^assets/([^/]+)/lang/zh_cn\.json$')
TEXT_EXT = {'.json', '.snbt', '.md', '.mdx', '.txt', '.js', '.mcmeta', '.url', '.sh',
            '.ps1', '.bat', '.toml', '.cfg', '.properties', '.gui', '.lang', '.html',
            '.xml', '.csv', '.yml', '.yaml', '.json5'}


class Ctx:
    def __init__(self, cfg, conv, vanilla_cn, vanilla_tw, overrides, mod_fill):
        self.cfg = cfg
        self.conv = conv
        self.vanilla_cn = vanilla_cn
        self.vanilla_tw = vanilla_tw
        self.overrides = overrides
        self.mod_fill = mod_fill          # {ns: {key: cn}}，模組自帶 zh_cn 的補位
        self.file_fill = {}               # {繁體路徑: 簡體位元組}，模組自帶 zh_cn 導覽書的補位
        self.renames = {k: v for k, v in cfg['renames'].items() if not k.startswith('_')}
        self.stats = {'lang_keys': 0, 'lang_vanilla': 0, 'lang_override': 0,
                      'lang_fill': 0, 'text_files': 0, 'binary_files': 0, 'fixups': 0}
        self.cjk_images = []
        self.banners = None               # gen_banners_tw.py 的產物目錄
        self.entity_names = {}            # 實體顯示名 cn → tw，給奖杯鍵用（見 _convert_key）


# ───────────────────────── 路徑 ─────────────────────────

def rename_component(c, ctx):
    c = c.replace('zh_cn', 'zh_tw')
    left = c
    for cn, tw in ctx.renames.items():
        c = c.replace(cn, tw)
        left = left.replace(cn, '')
    if CJK.search(left):
        raise SystemExit(f'❌ 檔名裡有 renames 表外的中文：{c!r}\n'
                         f'   請把它加進 src/zh_tw/config.json 的 renames。')
    return c


def rename_path(rel, ctx):
    return '/'.join(rename_component(p, ctx) for p in rel.split('/'))


# ───────────────────────── 文字 ─────────────────────────

def _walk_convert(obj, conv):
    if isinstance(obj, str):
        return conv.convert(obj)
    if isinstance(obj, list):
        return [_walk_convert(x, conv) for x in obj]
    if isinstance(obj, dict):
        return {conv.convert(k): _walk_convert(v, conv) for k, v in obj.items()}
    return obj


def convert_text(raw, rel, ctx):
    """整檔轉換。只動中日韓字元，所以換行（CRLF/LF）、縮排、BOM 全部原樣保留。"""
    bom = raw.startswith(b'\xef\xbb\xbf')
    text = raw.decode('utf-8-sig')
    if rel.endswith('.json') and CJK_ESCAPE.search(text):
        # 中文以 \uXXXX 跳脫寫成的 JSON，逐字轉換會漏掉，只能解析後再寫回
        data = json.loads(text)
        conv = _walk_convert(data, ctx.conv)
        if conv == data:
            return raw          # 跳脫的只是標點之類（如字型檔），沒有要轉的字就原樣保留
        text = json.dumps(conv, ensure_ascii=False, indent=2) + '\n'
    else:
        text = ctx.conv.convert(text)
    return (b'\xef\xbb\xbf' if bom else b'') + text.encode('utf-8')


def lang_value(k, v, ns, ctx, count=True):
    ov = ctx.overrides.get(ns, {})
    if k in ov:
        if count:
            ctx.stats['lang_override'] += 1
        return ov[k]
    if isinstance(v, str) and ctx.vanilla_cn.get(k) == v and k in ctx.vanilla_tw:
        if count:
            ctx.stats['lang_vanilla'] += 1
        return ctx.vanilla_tw[k]
    return _walk_convert(v, ctx.conv)


TROPHY_KEY = re.compile(r'^(.*) Trophy$')


def _convert_key(k, ctx):
    """鍵裡帶中文的語言條目（目前只有 hanhua_trophies）。

    奖杯名是把「實體顯示名 + ' Trophy'」烘焙進物品資料、再拿整串當翻譯鍵查的
    （見 scripts/gen_trophy_names.py）。單人遊戲烘焙的是**當下語言**的實體名，
    所以繁體世界會烘出「北極熊 Trophy」。轉出來的實體名必須與繁體版實際顯示的
    逐字一致，因此優先查實體名對照表，而不是對鍵整串做 OpenCC。
    """
    m = TROPHY_KEY.match(k)
    if m and m.group(1) in ctx.entity_names:
        return ctx.entity_names[m.group(1)] + ' Trophy'
    return ctx.conv.convert(k)


def scan_entity_names(rp_root, ctx):
    names = {}
    for k, v in ctx.vanilla_cn.items():
        if k.startswith('entity.minecraft.') and k.count('.') == 2 and k in ctx.vanilla_tw:
            names[v] = ctx.vanilla_tw[k]
    for f in sorted(Path(rp_root).glob('assets/*/lang/zh_cn.json')):
        ns = f.parts[-3]
        for k, v in json.loads(f.read_text(encoding='utf-8-sig')).items():
            if k.startswith('entity.') and isinstance(v, str):
                names[v] = lang_value(k, v, ns, ctx, count=False)
    ctx.entity_names = names


def convert_lang(raw, ns, ctx):
    data = json.loads(raw.decode('utf-8-sig'))
    ov = ctx.overrides.get(ns, {})
    out = {}
    for k, v in data.items():
        ctx.stats['lang_keys'] += 1
        tv = lang_value(k, v, ns, ctx)
        out[k] = tv
        if CJK.search(k):
            # 簡體鍵保留（簡體版時期已烘焙進存檔的奖杯），另加一條繁體鍵
            out.setdefault(_convert_key(k, ctx), tv)
    for k, v in ctx.mod_fill.pop(ns, {}).items():
        if k not in out:
            out[k] = ov.get(k, ctx.conv.convert(v))
            ctx.stats['lang_fill'] += 1
    return (json.dumps(out, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


# ───────────────────────── 特別處理 ─────────────────────────

def _sub_exact(text, old, new, rel, expect=None):
    n = text.count(old)
    if n == 0 or (expect is not None and n != expect):
        raise SystemExit(f'❌ {rel}：預期「{old}」出現 {expect or "≥1"} 次，實際 {n} 次。'
                         f'上游可能改了這個檔案，請檢查 build_tw.py 的 FIXUPS。')
    return text.replace(old, new)


def _repo(text, rel, ctx):
    return _sub_exact(text, ctx.cfg['upstream_repo'], ctx.cfg['repo'], rel)


def _installer(text, rel, ctx):
    text = _repo(text, rel, ctx)
    # 安裝器裡的 zh_cn 全是路徑／檔名／options.txt 的 lang 值，沒有別的語意
    return _sub_exact(text, 'zh_cn', 'zh_tw', rel)


def _pack_check(text, rel, ctx):
    return _sub_exact(text, "const LANG_PATH = 'lang/zh_cn.json'",
                      "const LANG_PATH = 'lang/zh_tw.json'", rel, expect=1)


def _vp_config(text, rel, ctx):
    return _sub_exact(text, '"default_language": "zh_cn"', '"default_language": "zh_tw"',
                      rel, expect=1)


def _readme(text, rel, ctx):
    return ctx.cfg['readme_notice'] + text


# (路徑比對, 轉換「前」套用的修正)。修正在簡體原文上做，之後才整檔轉換。
FIXUPS = [
    (re.compile(r'(^|/)install\.(sh|ps1)$'), _installer),
    (re.compile(r'(^|/)kubejs/client_scripts/hanhua_update_check\.js$'), _repo),
    (re.compile(r'(^|/)kubejs/client_scripts/hanhua_pack_check\.js$'), _pack_check),
    (re.compile(r'(^|/)config/fancymenu/customization/title_screen_layout\.txt$'), _repo),
    (re.compile(r'\.url$'), _repo),
    (re.compile(r'(^|/)config/vaultpatcher_asm/config\.json$'), _vp_config),
    (re.compile(r'(^|/)请安装前务必看我\.md$'), _readme),
]

# 資源蜂腳本裡這兩張表的鍵是「拿來比對的既有名字」：
#   PB_SYS       系統產生的蜂名（用來分辨玩家自訂名，玩家命名的絕不改）
#   PB_ZH_ALIAS  舊版譯名 → 新譯名
# 玩家存檔裡的蜂籠可能是簡體版時期寫進去的，所以鍵要「簡體＋繁體」兩份都在，值轉繁體。
PB_UNION_RE = re.compile(r'^(const (?:PB_SYS|PB_ZH_ALIAS) = )(\{.*\});\s*$')


def _convert_pb_script(raw, rel, ctx):
    text = raw.decode('utf-8')
    out = []
    hits = 0
    for line in text.splitlines(keepends=True):
        m = PB_UNION_RE.match(line.rstrip('\r\n'))
        if not m:
            out.append(ctx.conv.convert(line))
            continue
        hits += 1
        table = json.loads(m.group(2))
        merged = {}
        for k, v in table.items():
            v2 = ctx.conv.convert(v) if isinstance(v, str) else v
            merged[k] = v2
            merged.setdefault(ctx.conv.convert(k), v2)
        eol = line[len(line.rstrip('\r\n')):]
        out.append(m.group(1) + json.dumps(merged, ensure_ascii=False) + ';' + eol)
    if hits == 0:
        raise SystemExit(f'❌ {rel}：找不到 PB_SYS / PB_ZH_ALIAS，生成器格式可能變了')
    ctx.stats['fixups'] += 1
    return ''.join(out).encode('utf-8')


def _convert_mcmeta(raw, rel, ctx):
    data = json.loads(raw.decode('utf-8-sig'))
    data['pack']['description'] = ctx.conv.convert(data['pack']['description']) + '（繁體中文）'
    lang_def = {k: v for k, v in ctx.cfg['language_def'].items() if not k.startswith('_')}
    if 'language' in data:
        data['language'].pop('zh_cn', None)
        data['language'].update(lang_def)
    ctx.stats['fixups'] += 1
    return (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


# ───────────────────────── 走樹 ─────────────────────────

def process_file(src, rel, ctx):
    raw = src.read_bytes()
    m = LANG_RE.match(rel)
    if m:
        return convert_lang(raw, m.group(1), ctx)
    if rel == 'pack.mcmeta':
        return _convert_mcmeta(raw, rel, ctx)
    if re.search(r'(^|/)kubejs/(client|server)_scripts/pb_hanhua_[^/]*\.js$', rel) \
            and b'PB_SYS' in raw:
        return _convert_pb_script(raw, rel, ctx)
    if re.match(r'^assets/[^/]+/font/', rel):
        # 字型定義裡的中文是「字形表」不是文字：cjk-punctuations.json 為簡體元素字
        # （𬭛𬬻…）提供點陣。繁體元素字（𨨏鑪…）原版 Unifont 15.1 全都有，不需要另畫。
        ctx.stats['binary_files'] += 1
        return raw
    ext = os.path.splitext(rel)[1].lower()
    if ext not in TEXT_EXT:
        if ext == '.png' and re.search(r'(^|/)config/fancymenu/assets/[^/]+\.png$', rel):
            import images_tw    # 只有碰到圖才需要 Pillow 與繁體字型
            out = images_tw.redraw_menu_button(raw, rel)
            if out is not None:
                ctx.stats['images_redrawn'] = ctx.stats.get('images_redrawn', 0) + 1
                return out
        m = re.match(r'^assets/atm/textures/questpics/(.+\.png)$', rel)
        if m and ctx.banners and (ctx.banners / m.group(1)).exists():
            ctx.stats['images_redrawn'] = ctx.stats.get('images_redrawn', 0) + 1
            return (ctx.banners / m.group(1)).read_bytes()
        if ext == '.png' and _png_has_cjk_hint(rel):
            ctx.cjk_images.append(rel)
        ctx.stats['binary_files'] += 1
        return raw
    for pat, fn in FIXUPS:
        if pat.search(rel):
            text = raw.decode('utf-8-sig')
            bom = raw.startswith(b'\xef\xbb\xbf')
            text = fn(text, rel, ctx)
            raw = (b'\xef\xbb\xbf' if bom else b'') + text.encode('utf-8')
            ctx.stats['fixups'] += 1
    ctx.stats['text_files'] += 1
    return convert_text(raw, rel, ctx)


def _png_has_cjk_hint(rel):
    # 烤進中文字的圖：任務橫幅、主選單按鈕、模組貼圖重繪。第一階段原樣沿用簡體圖，
    # 這裡只列出來，之後由圖片生成器改用繁體字串重繪。
    return any(s in rel for s in ('questpics', 'fancymenu/assets', 'textures/gui', 'title'))


def process_tree(src_root, dst_root, ctx, inner_zip_hook):
    for dp, dns, fns in os.walk(src_root):
        dns.sort()
        for fn in sorted(fns):
            src = Path(dp) / fn
            rel = src.relative_to(src_root).as_posix()
            new_rel = rename_path(rel, ctx)
            dst = dst_root / new_rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if fn.endswith('.zip') and '/resourcepacks/' in '/' + rel:
                inner_zip_hook(src, dst)
                continue
            dst.write_bytes(process_file(src, rel, ctx))
            if os.access(src, os.X_OK):
                dst.chmod(0o755)


def _mkzip(out, src, prefix=None):
    cmd = [sys.executable, str(ROOT / 'scripts' / 'mkzip.py'), str(out), str(src)]
    if prefix:
        cmd.append(prefix)
    subprocess.run(cmd, check=True)


def convert_zip(zpath, out_dir, ctx, work):
    name = zpath.name
    if 'zh_cn' not in name:
        raise SystemExit(f'❌ 不是簡體出貨包：{name}')
    out_name = name.replace('zh_cn', 'zh_tw')
    stage_in = work / ('in-' + name)
    stage_out = work / ('out-' + name)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(stage_in)
    tops = [p for p in stage_in.iterdir()]
    if len(tops) != 1 or not tops[0].is_dir():
        raise SystemExit(f'❌ {name}：zip 根目錄應該只有一個資料夾')
    top_new = rename_component(tops[0].name, ctx)

    def inner(src_zip, dst_zip):
        rp_in = work / ('rp-in-' + src_zip.stem)
        rp_out = work / ('rp-out-' + src_zip.stem)
        with zipfile.ZipFile(src_zip) as z:
            z.extractall(rp_in)
        scan_entity_names(rp_in, ctx)
        process_tree(rp_in, rp_out, ctx, None)
        # 模組自帶 zh_cn 補位裡，資源包本來沒有那個命名空間的語言檔 → 新開一份
        for ns in sorted(list(ctx.mod_fill)):
            p = rp_out / 'assets' / ns / 'lang' / 'zh_tw.json'
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(convert_lang(b'{}', ns, ctx))
        for rel, raw in sorted(ctx.file_fill.items()):
            p = rp_out / rel
            if p.exists():        # 資源包自己有（簡體版譯過的那份）就以它為準
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(convert_text(raw, rel, ctx))
            ctx.stats['file_fill'] = ctx.stats.get('file_fill', 0) + 1
        _mkzip(dst_zip, rp_out)

    process_tree(tops[0], stage_out / top_new, ctx, inner)
    out = out_dir / out_name
    _mkzip(out, stage_out / top_new, top_new)
    return out


# ───────────────────────── 輸入 ─────────────────────────

def load_vanilla():
    g = lambda n: json.loads(vanilla.asset_object('/nonexistent', n).decode('utf-8-sig'))
    return g('minecraft/lang/zh_cn.json'), g('minecraft/lang/zh_tw.json')


BOOK_SEG = re.compile(r'(^|/)_?zh_cn(/|$)')
BOOK_EXT = ('.json', '.md', '.mdx', '.txt', '.snbt', '.gui')


def collect_mod_fill(mods_dir, pack_zip):
    """模組自帶 zh_cn 有、簡體資源包沒覆蓋、模組自己也沒 zh_tw 的內容。

    回傳 (語言鍵 {ns: {key: cn}}, 導覽書檔 {繁體路徑: 簡體位元組})。
    導覽書（Patchouli / AE2 Guide / Oracle Index…）是按語言目錄整份放的：
    簡體版刪掉了「與模組自帶 zh_cn 逐位元組相同」的頁（遊戲會讀模組那份），
    也沒收模組自己已經譯好的書——這些到 zh_tw 都會回落成英文，所以一併轉換補上。
    """
    pack = {}
    with zipfile.ZipFile(pack_zip) as z:
        pack_names = set(z.namelist())
        for n in pack_names:
            m = LANG_RE.match(n)
            if m:
                pack[m.group(1)] = json.loads(z.read(n).decode('utf-8-sig'))
    fill = {}
    files = {}
    for j in sorted(Path(mods_dir).glob('*.jar')):
        try:
            z = zipfile.ZipFile(j)
        except zipfile.BadZipFile:
            continue
        with z:
            names = set(z.namelist())
            for n in names:
                m = LANG_RE.match(n)
                if not m:
                    if (n.startswith('assets/') and n.endswith(BOOK_EXT) and BOOK_SEG.search(n)
                            and n not in pack_names):
                        tw = BOOK_SEG.sub(lambda g: g.group(0).replace('zh_cn', 'zh_tw'), n)
                        if tw not in names and tw not in files:
                            files[tw] = z.read(n)
                    continue
                ns = m.group(1)
                try:
                    # strict=False：有模組（RootsClassic）的 zh_cn 字串裡夾著原始控制字元，
                    # 遊戲的 GSON 照讀不誤，這裡也照讀
                    cn = json.loads(z.read(n).decode('utf-8-sig'), strict=False)
                    twn = f'assets/{ns}/lang/zh_tw.json'
                    tw = json.loads(z.read(twn).decode('utf-8-sig')) if twn in names else {}
                except (ValueError, UnicodeDecodeError) as e:
                    print(f'  ⚠️ 略過無法解析的語言檔 {j.name}!{n}：{e}')
                    continue
                have = pack.get(ns, {})
                for k, v in cn.items():
                    if k in have or k in tw or not isinstance(v, str) or k.startswith('/'):
                        continue
                    if not CJK.search(v):
                        continue
                    fill.setdefault(ns, {})[k] = v
    return fill, files


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('zips', nargs='+', type=Path)
    ap.add_argument('--out', type=Path, default=ROOT / 'dist')
    ap.add_argument('--mods', type=Path, help='整合包 mods/ 目錄；給了才做模組自帶 zh_cn 的補位')
    ap.add_argument('--banners', type=Path,
                    help='gen_banners_tw.py 產出的繁體橫幅目錄（build/zh_tw/questpics）')
    args = ap.parse_args()

    cfg = json.loads((SRC_TW / 'config.json').read_text(encoding='utf-8'))
    ov = json.loads((SRC_TW / 'overrides.json').read_text(encoding='utf-8'))['lang']
    terms, post, exclude, rules = load_terms()
    conv = Converter(terms, post, rules=rules)
    vcn, vtw = load_vanilla()
    renames = [(k, v) for k, v in cfg['renames'].items() if not k.startswith('_')]
    conv.set_name_dict(build_name_dict(conv, vcn, vtw, exclude, extra=renames))
    print(f'詞表 {len(terms)} 條，名稱字典 {len(conv.name_dict)} 條')

    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='atm10-zh_tw-') as tmp:
        work = Path(tmp)
        for z in args.zips:
            mod_fill = {}
            if args.mods and '-client-' in z.name:
                with zipfile.ZipFile(z) as outer:
                    rp = [n for n in outer.namelist()
                          if '/resourcepacks/' in n and n.endswith('.zip')]
                    if len(rp) != 1:
                        raise SystemExit(f'❌ {z.name}：找不到唯一的資源包 zip')
                    rp_tmp = work / 'probe-rp.zip'
                    rp_tmp.write_bytes(outer.read(rp[0]))
                mod_fill, file_fill = collect_mod_fill(args.mods, rp_tmp)
                print(f'模組自帶 zh_cn 補位：{sum(map(len, mod_fill.values()))} 條，'
                      f'{len(mod_fill)} 個命名空間；導覽書 {len(file_fill)} 檔')
            ctx = Ctx(cfg, conv, vcn, vtw, ov, mod_fill)
            if args.mods and '-client-' in z.name:
                ctx.file_fill = file_fill
            if args.banners:
                if not args.banners.is_dir():
                    raise SystemExit(f'❌ --banners 目錄不存在：{args.banners}')
                ctx.banners = args.banners
            out = convert_zip(z, args.out, ctx, work)
            print(f'✅ {out}')
            print('   ' + '  '.join(f'{k}={v}' for k, v in ctx.stats.items()))
            if ctx.cjk_images:
                print(f'   ⚠️ {len(ctx.cjk_images)} 張圖可能烤著簡體字，仍沿用簡體圖'
                      f'（例：{ctx.cjk_images[0]}）')


if __name__ == '__main__':
    main()
