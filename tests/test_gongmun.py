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
from gongmun import build_gongmun  # noqa: E402

TEMPLATE = os.path.join(ROOT, 'skill', 'auc-docs', 'templates', 'gongmun.hwpx')
FIX = os.path.join(ROOT, 'tests', 'fixtures')


def load(name):
    with open(os.path.join(FIX, name), encoding='utf-8') as f:
        return json.load(f)


def build(spec):
    d = tempfile.mkdtemp()
    out = os.path.join(d, 'o.hwpx')
    build_gongmun(spec, TEMPLATE, out)
    return hwpx_io.read_section(out)[1]


def body_lines(xml):
    """본문 누름틀 구간의 최상위 문단 텍스트(머리 표 제외)."""
    head, paras, tail = hwpx_io.split_section(xml)
    lines = []
    for i, p in enumerate(paras[:-1]):
        if i == 0:
            p = p[p.rfind('</hp:tbl>'):]
        lines.append(hwpx_io.para_text(p))
    return lines


class GongmunTest(unittest.TestCase):
    def test_futsal_text(self):
        xml = build(load('gongmun_futsal.json'))
        lines = body_lines(xml)
        self.assertTrue(lines[0].startswith('1. 최근 풋살'))
        self.assertTrue(lines[1].startswith('2. 이에 따라, 유사 사고'))
        self.assertIn('<주요 점검 사항>', lines[2])
        self.assertIn('발견된 위험 요소에 대한 즉시 안전 조치', lines[2])
        self.assertTrue(lines[3].startswith('3. 아울러'))
        self.assertTrue(lines[3].endswith('바랍니다.  끝.'))
        self.assertEqual(hwpx_io.para_text(xml).count('끝.'), 1)
        self.assertIn('풋살장 안전사고 발생 관련 안전점검 실시 요청', hwpx_io.para_text(xml))

    def test_attachments(self):
        spec = load('gongmun_futsal.json')
        spec['attachments'] = ['점검표', '사진']
        lines = body_lines(build(spec))
        self.assertTrue(lines[3].endswith('바랍니다.'))
        self.assertEqual(lines[4], '붙임  1. 점검표 1부.')
        self.assertEqual(lines[5].strip(), '2. 사진 1부.  끝.')

    def test_one_item_with_single_attachment(self):
        xml = build(load('gongmun_one_item.json'))
        head, paras, tail = hwpx_io.split_section(xml)
        self.assertEqual(xml.count('<hp:fieldBegin'), 1)
        self.assertEqual(xml.count('<hp:fieldEnd'), 1)
        lines = body_lines(xml)
        self.assertEqual(lines[-1], '붙임  회의 개최 계획 & 참석 명단 1부.  끝.')
        self.assertIn('&amp; 참석', xml)
        self.assertIn('부분공개', hwpx_io.para_text(paras[-1]))

    def test_box_last_gets_end_line(self):
        spec = load('gongmun_futsal.json')
        spec['body'] = spec['body'][:3]
        lines = body_lines(build(spec))
        self.assertEqual(lines[-1].strip(), '끝.')

    def test_sub_items(self):
        spec = load('gongmun_one_item.json')
        spec['attachments'] = []
        spec['body'][0]['sub'] = [{'text': [['일시: 2026. 11. 3.', False]],
                                   'sub': [{'text': [['세부', False]]}]},
                                  {'text': [['장소: 대회의실', False]]}]
        lines = body_lines(build(spec))
        self.assertEqual([l.strip() for l in lines],
                         ['1. 2026. 11. 3.(화) 14:00 대회의실 사용에 협조하여 주시기 바랍니다.',
                          '가. 일시: 2026. 11. 3.', '1) 세부', '나. 장소: 대회의실  끝.'])

    def test_emphasis(self):
        xml = build(load('gongmun_futsal.json'))
        self.assertRegex(xml, r'<hp:run charPrIDRef="22"><hp:t>유사 사고 방지를')

    def test_footer(self):
        xml = build(load('gongmun_futsal.json'))
        footer = hwpx_io.para_text(hwpx_io.split_section(xml)[1][-1])
        for s in ['종합운동장사업부장, 동안체육사업부장, 만안체육사업부장', '★담당자', '안전감사팀장',
                  '사장', '안전감사팀-○○', '○○○@auc.or.kr', '031-389-○○○○',
                  '경기도 안양시 동안구 평촌대로 389', '안양도시공사사장']:
            self.assertIn(s, footer)

    def test_too_many_approvers(self):
        spec = load('gongmun_futsal.json')
        spec['approvers'] = ['a', 'b', 'c', 'd', 'e']
        with self.assertRaises(ValueError):
            build(spec)


if __name__ == '__main__':
    unittest.main()
