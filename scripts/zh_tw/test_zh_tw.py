#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# atm10-zh-tw — All the Mods 10 繁體中文（台灣）版
# SPDX-License-Identifier: GPL-3.0-or-later
"""繁體轉換與閘門的反例測試。

每條都對應一次實際踩過（或差點踩到）的坑：

| 反例 | 坑 |
|---|---|
| 色碼緊貼中文「&#4497DB超频」 | OpenCC 詞庫的「B超→超音波」吃掉色碼字母 |
| 「深色橡木窗户板」 | 原版整條名稱「黑橡木塊」被當詞套進模組名 |
| 「粗铁块」 | 上下文規則搶在原版官方名之前命中 |
| 「清理了 $hit 个旧版本」 | OpenCC 把「个旧」當地名「箇舊」 |
| 原文帶輔助私用區字元 | 與佔位符衝突，必須報錯而不是默默弄壞 |
| 殘留簡體字的包 | 閘門必須紅 |
| 色碼被改的包 | 骨架對照必須紅 |
| 取不到原版 zh_tw | 判據不在時閘門必須紅，不許放行 |
| 上游改了安裝器（找不到要換的字串） | 特別處理必須報錯，不許靜默略過 |

用法:
    python3 scripts/zh_tw/test_zh_tw.py
"""
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0]))

import build_tw  # noqa: E402
import check_tw  # noqa: E402
from converter import Converter, build_name_dict, load_terms  # noqa: E402

_TERMS = load_terms()
_VANILLA = None


def conv(with_names=True):
    global _VANILLA
    terms, post, exclude, rules = _TERMS
    c = Converter(terms, post, rules=rules)
    if with_names:
        if _VANILLA is None:
            _VANILLA = build_tw.load_vanilla()
        c.set_name_dict(build_name_dict(c, *_VANILLA, exclude))
    return c


def make_zip(path, files, inner_rp=None):
    with zipfile.ZipFile(path, 'w') as z:
        for n, data in files.items():
            z.writestr(n, data)
        if inner_rp is not None:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w') as r:
                for n, data in inner_rp.items():
                    r.writestr(n, data)
            z.writestr('atm10-zh_tw-client/resourcepacks/ATM10漢化包-8.1.zip', buf.getvalue())


class ConverterTest(unittest.TestCase):
    def test_color_code_survives(self):
        self.assertEqual(conv(False).convert('&#4497DB超频模块'), '&#4497DB超頻模組')
        self.assertEqual(conv(False).convert('U盘'), 'U盤')

    def test_vanilla_terms(self):
        c = conv()
        self.assertEqual(c.convert('下界合金锭'), '獄髓錠')
        self.assertEqual(c.convert('远古残骸'), '遠古遺骸')
        self.assertEqual(c.convert('橡木台阶'), '橡木半磚')

    def test_name_dict_is_not_a_morpheme(self):
        self.assertEqual(conv().convert('深色橡木窗户板'), '黑橡木窗戶板')

    def test_name_dict_beats_rules(self):
        c = conv()
        self.assertEqual(c.convert('粗铁块'), '鐵原礦方塊')
        self.assertEqual(c.convert('粗铀'), '鈾原礦')

    def test_context_rules(self):
        c = conv(False)
        self.assertEqual(c.convert('击败凋灵后'), '擊敗凋零怪後')
        self.assertEqual(c.convert('凋灵合金'), '凋零合金')
        self.assertEqual(c.convert('蜂后和皇后'), '蜂后和皇后')

    def test_opencc_place_name(self):
        self.assertEqual(conv(False).convert('清理了 $hit 个旧版本'), '清理了 $hit 個舊版本')

    def test_taiwan_quotes(self):
        c = conv(False)
        self.assertEqual(c.convert('点击“搜索”按钮'), '點選「搜尋」按鈕')
        self.assertEqual(c.convert('他说“这是‘内层’引号”'), '他說「這是『內層』引號」')
        self.assertEqual(c.convert('输入“%s”即可'), '輸入「%s」即可')
        self.assertEqual(c.convert('Explorer’s 罗盘'), 'Explorer’s 羅盤')       # 撇號不動
        self.assertEqual(c.convert('设置‘renderHunger’为假'), '設定‘renderHunger’為假')
        self.assertEqual(c.convert('只有“左引号'), '只有“左引號')                 # 不成對不動

    def test_pua_input_is_rejected(self):
        with self.assertRaises(ValueError):
            conv(False).convert('铁\U000F0001块')


class GateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_residual_simplified_is_red(self):
        z = self.tmp / 'atm10-zh_tw-client-r1-atm8.1.zip'
        make_zip(z, {'atm10-zh_tw-client/config/a.snbt': 'title: "铁锭"'})
        bad, _, _ = check_tw.check_zip(z, check_tw.simplified_detector())
        self.assertTrue(bad)

    def test_clean_package_is_green(self):
        z = self.tmp / 'atm10-zh_tw-client-r1-atm8.1.zip'
        make_zip(z, {'atm10-zh_tw-client/config/a.snbt': 'title: "鐵錠、台、傢伙"'})
        bad, _, _ = check_tw.check_zip(z, check_tw.simplified_detector())
        self.assertFalse(bad)

    def test_skeleton_change_is_red(self):
        cn = self.tmp / 'atm10-zh_cn-client-r1-atm8.1.zip'
        tw = self.tmp / 'atm10-zh_tw-client-r1-atm8.1.zip'
        make_zip(cn, {'atm10-zh_cn-client/config/a.snbt': '"&#4497DB超频"'})
        make_zip(tw, {'atm10-zh_tw-client/config/a.snbt': '"&#4497D超音波頻"'})
        self.assertTrue(check_tw.check_skeleton(cn, tw, {}))

    def test_missing_file_is_red(self):
        cn = self.tmp / 'atm10-zh_cn-client-r1-atm8.1.zip'
        tw = self.tmp / 'atm10-zh_tw-client-r1-atm8.1.zip'
        make_zip(cn, {'atm10-zh_cn-client/a.snbt': '铁', 'atm10-zh_cn-client/b.snbt': '铜'})
        make_zip(tw, {'atm10-zh_tw-client/a.snbt': '鐵'})
        self.assertTrue(check_tw.check_skeleton(cn, tw, {}))

    def test_no_vanilla_is_red(self):
        with mock.patch.object(check_tw.vanilla, 'asset_object', side_effect=OSError('offline')):
            with self.assertRaises(SystemExit) as e:
                check_tw.simplified_detector()
        self.assertNotEqual(e.exception.code, 0)


class FixupTest(unittest.TestCase):
    def ctx(self):
        cfg = json.loads((HERE.parents[1] / 'src' / 'zh_tw' / 'config.json').read_text(encoding='utf-8'))
        return build_tw.Ctx(cfg, conv(False), {}, {}, {}, {})

    def test_upstream_changed_installer_is_red(self):
        with self.assertRaises(SystemExit):
            build_tw._installer('echo hello', 'install.sh', self.ctx())

    def test_installer_rewrite(self):
        src = 'REPO="chiba233/atm10-zh-cn"\nprintf \'lang:zh_cn\\n\'\n'
        out = build_tw._installer(src, 'install.sh', self.ctx())
        self.assertIn('George15526/atm10-zh-tw', out)
        self.assertIn('lang:zh_tw', out)
        self.assertNotIn('zh_cn', out)

    def test_pb_tables_keep_both_scripts(self):
        js = ('const PB_SYS = {"玛瑙蜜蜂": 1, "Agate Bee": 1};\n'
              'const PB_ID2ZH = {"agate": "玛瑙蜜蜂"};\n').encode('utf-8')
        out = build_tw._convert_pb_script(js, 'kubejs/client_scripts/pb_hanhua_tooltip.js',
                                          self.ctx()).decode('utf-8')
        sys_line = out.splitlines()[0]
        self.assertIn('玛瑙蜜蜂', sys_line)        # 簡體版時期烘焙的舊名仍認得
        self.assertIn('瑪瑙蜜蜂', sys_line)
        self.assertIn('"agate": "瑪瑙蜜蜂"', out)

    def test_mod_fill_books_and_keys(self):
        tmp = Path(tempfile.mkdtemp())
        mods = tmp / 'mods'
        mods.mkdir()
        make_zip(mods / 'x.jar', {
            'assets/x/lang/zh_cn.json': '{"a": "铁锭", "b": "铜锭", "c": "金锭", "d": "结构罗盘"}',
            'assets/x/lang/zh_tw.json': '{"c": "金錠（模組自己的繁中）", "d": "Explorer\'s Compass"}',
            'assets/x/patchouli_books/g/zh_cn/entries/e.json': '{"name": "入门"}',
            'assets/x/patchouli_books/g/zh_cn/entries/f.json': '{"name": "进阶"}',
            'assets/x/patchouli_books/g/zh_tw/entries/f.json': '{"name": "進階"}',
            'assets/x/ae2guide/_zh_cn/p.md': '# 页面',
        })
        rp = tmp / 'rp.zip'
        make_zip(rp, {'assets/x/lang/zh_cn.json': '{"a": "铁锭"}'})
        keys, files = build_tw.collect_mod_fill(mods, rp)
        # a 簡體包有、c 模組自己有繁中；d 的模組 zh_tw 只是英文佔位，照樣補
        self.assertEqual(keys, {'x': {'b': '铜锭', 'd': '结构罗盘'}})
        self.assertEqual(set(files), {'assets/x/patchouli_books/g/zh_tw/entries/e.json',
                                      'assets/x/ae2guide/_zh_tw/p.md'})

    def test_unknown_cjk_filename_is_red(self):
        with self.assertRaises(SystemExit):
            build_tw.rename_component('新的说明.md', self.ctx())


if __name__ == '__main__':
    unittest.main(verbosity=2)
