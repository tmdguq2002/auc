import copy
import json
import os
import re
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'skill', 'auc-docs', 'scripts'))
import hwpx_io  # noqa: E402
from report import build_report  # noqa: E402

TEMPLATE = os.path.join(ROOT, 'skill', 'auc-docs', 'templates', 'report.hwpx')


def spec():
    with open(os.path.join(ROOT, 'tests', 'fixtures', 'report_tft.json'), encoding='utf-8') as f:
        return json.load(f)


def build(s):
    out = os.path.join(tempfile.mkdtemp(), 'o.hwpx')
    build_report(s, TEMPLATE, out)
    return hwpx_io.read_section(out)[1]


def tables(xml):
    return re.findall(r'<hp:tbl\b.*?</hp:tbl>', xml, re.S)


class ReportTest(unittest.TestCase):
    def test_structure(self):
        xml = build(spec())
        paras = [hwpx_io.para_text(p) for p in hwpx_io.split_section(xml)[1]]
        heads = [p for p in paras if re.match(r'^[ⅠⅡⅢⅣⅤ]', p)]
        self.assertEqual(heads, ['Ⅰ회의개요', 'Ⅱ주요 논의결과', 'Ⅲ사진대지', 'Ⅳ향후계획'])
        nums = [p for p in paras if re.match(r'^ \d+\. ', p)]
        self.assertEqual(nums, [' 1. 시설별 에너지 사용현황 및 감축방안 점검', ' 2. 에너지 사용 관리대장 시범운영'])
        self.assertIn('  일    시 : 2026. 10. 22.(목)', paras)
        self.assertIn('  - 지방공기업 경영평가 친환경경영 지표 및 평가 대응방향 공유', paras)
        self.assertIn('※ 시설 운영 및 이용객 안전·서비스에 지장이 없는 범위에서 추진', paras)
        self.assertEqual(xml.count('<hp:fieldBegin'), 1)
        self.assertEqual(xml.count('<hp:fieldEnd'), 1)
        self.assertIn('<hp:fieldEnd', hwpx_io.split_section(xml)[1][-1])

    def test_num_restarts_per_section(self):
        s = spec()
        s['sections'][0]['blocks'].insert(0, {'num': '개요'})
        paras = [hwpx_io.para_text(p) for p in hwpx_io.split_section(build(s))[1]]
        self.assertEqual([p for p in paras if re.match(r'^ \d+\. ', p)][:2], [' 1. 개요', ' 1. 시설별 에너지 사용현황 및 감축방안 점검'])

    def test_emphasis(self):
        self.assertIn('<hp:run charPrIDRef="16"><hp:t>온실가스 목표관리 대상시설</hp:t></hp:run>', build(spec()))

    def test_table_columns(self):
        for n in (3, 6, 8):
            s = spec()
            s['sections'] = [{'title': 't', 'blocks': [{'table': {
                'header': ['h%d' % i for i in range(n)],
                'rows': [['r%d%d' % (r, i) for i in range(n)] for r in range(2)]}}]}]
            xml = build(s)
            body = hwpx_io.split_section(xml)[1]
            tbl = [t for p in body[3:] for t in tables(p) if 'h0' in t][0]
            self.assertIn('rowCnt="3" colCnt="%d"' % n, tbl)
            self.assertEqual(len(re.findall(r'<hp:tc\b', tbl)), 3 * n)
            widths = [int(w) for w in re.findall(r'<hp:cellSz width="(\d+)"', tbl)[:n]]
            self.assertEqual(sum(widths), 46216)
            self.assertIn('r1%d' % (n - 1), hwpx_io.para_text(tbl))

    def test_cover(self):
        xml = build(spec())
        cover = hwpx_io.para_text(hwpx_io.split_section(xml)[1][0])
        for s in ['온실가스 감축 TFT 회의 결과보고', '전략기획부-○○', '전략기획부', '★담당자', '전략기획부장', '공개']:
            self.assertIn(s, cover)

    def test_photo_placeholder(self):
        xml = build(spec())
        self.assertIn('온실가스 감축 TFT 회의', xml)
        self.assertNotIn('<hp:pic', ''.join(hwpx_io.split_section(xml)[1][3:]))

    def test_schedule_tab(self):
        xml = build(spec())
        self.assertRegex(xml, r'에너지 사용 관리대장 시범운영</hp:t></hp:run><hp:run charPrIDRef="12"><hp:t> <hp:tab [^>]*/> 2026\.11월')

    def test_object_ids_unique(self):
        ids = re.findall(r'<hp:(?:tbl|pic|rect) id="(\d+)"', build(spec()))
        self.assertEqual(len(ids), len(set(ids)))

    def test_unknown_block(self):
        s = spec()
        s['sections'][0]['blocks'].append({'chart': 'x'})
        with self.assertRaises(ValueError):
            build(s)


if __name__ == '__main__':
    unittest.main()
