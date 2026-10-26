import json
import os
import re
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'skill', 'auc-docs', 'scripts'))
import build_hwpx  # noqa: E402
import hwpx_io  # noqa: E402


def load(name):
    with open(os.path.join(ROOT, 'tests', 'fixtures', name), encoding='utf-8') as f:
        return json.load(f)


def build(s):
    out = os.path.join(tempfile.mkdtemp(), 'o.hwpx')
    build_hwpx.build(s, out)
    return hwpx_io.read_section(out)[1]


def texts(xml):
    return [hwpx_io.para_text(p) for p in hwpx_io.split_section(xml)[1]]


class YojiTest(unittest.TestCase):
    def test_single_page(self):
        for name in ('yoji_event.json', 'yoji_law.json'):
            xml = build(load(name))
            paras = hwpx_io.split_section(xml)[1]
            heads = [p for p in paras if '존중과 성장의 안양도시공사' in hwpx_io.para_text(p)]
            self.assertEqual(len(heads), 1, name)
            self.assertNotIn('pageBreak="1"', xml, name)
            self.assertEqual(xml.count('<hp:secPr'), 1)

    def test_pages_rejected(self):
        with self.assertRaisesRegex(ValueError, '한 장'):
            build({'type': 'yoji', 'pages': [load('yoji_event.json'), load('yoji_law.json')]})

    def test_blocks(self):
        t = texts(build(load('yoji_event.json')))
        self.assertIn(' ❍ 시    간 : 11:00 ~ 13:00', t)
        self.assertIn('  - 춘(春)나게 걷기 : 잣나무 숲까지 봄 향기를 맡으며 이동', t)
        t = texts(build(load('yoji_law.json')))
        self.assertIn(' ※ 법 시행 이후 처벌받은 공공기관장 없음', t)

    def test_emphasis(self):
        self.assertIn('<hp:run charPrIDRef="34"><hp:t>춘(春)나게 걷기</hp:t></hp:run>', build(load('yoji_event.json')))
        self.assertIn('<hp:run charPrIDRef="34"><hp:t>경영책임자</hp:t></hp:run>', build(load('yoji_law.json')))

    def test_labels(self):
        self.assertIn('개  요', texts(build(load('yoji_event.json'))))
        self.assertIn('현  황', texts(build(load('yoji_law.json'))))

    def test_header_cells(self):
        xml = build(load('yoji_event.json'))
        head = [p for p in hwpx_io.split_section(xml)[1] if '존중과 성장' in hwpx_io.para_text(p)][0]
        cells = [hwpx_io.para_text(c) for c in re.findall(r'<hp:tc\b.*?</hp:tc>', head, re.S)]
        self.assertEqual(cells[1:], ['2026. 3. 27.(금)', '안전감사팀'])

    def test_table(self):
        xml = build(load('yoji_law.json'))
        tbl = re.search(r'<hp:tbl\b(?:(?!</hp:tbl>).)*2022년 3월.*?</hp:tbl>', xml, re.S).group()
        self.assertIn('rowCnt="3" colCnt="2"', tbl)
        cells = re.findall(r'<hp:tc\b.*?</hp:tc>', tbl, re.S)
        body = {re.search(r'colAddr="(\d+)" rowAddr="(\d+)"', c).groups(): re.search(r'paraPrIDRef="(\d+)"', c).group(1) for c in cells}
        self.assertEqual(body[('0', '1')], '40')  # 일자: 가운데
        self.assertEqual(body[('1', '1')], '43')  # 개요: 원본 둘째 열 문단 모양

    def test_photo(self):
        xml = build(load('yoji_event.json'))
        photo = [p for p in hwpx_io.split_section(xml)[1] if '도보 이동거리' in hwpx_io.para_text(p)][0]
        self.assertNotIn('<hp:pic', photo)
        self.assertIn('관악산 산림욕장(잣나무숲)', hwpx_io.para_text(photo))
        heights = [int(x) for x in re.findall(r'<hp:cellSz width="\d+" height="(\d+)"', photo)]
        self.assertGreaterEqual(min(heights[:2]), 16000)

    def test_two_reference_styles(self):
        p1 = [p for p in hwpx_io.split_section(build(load('yoji_event.json')))[1] if hwpx_io.para_text(p).startswith(' ❍ 시')][0]
        p2 = [p for p in hwpx_io.split_section(build(load('yoji_law.json')))[1] if hwpx_io.para_text(p).startswith(' ❍ 처벌대상')][0]
        self.assertIn('paraPrIDRef="39"', p1)  # 글 위주(첫 참고 쪽): 줄간격 200%
        self.assertIn('paraPrIDRef="41"', p2)  # 표 위주(둘째 참고 쪽): 160%

    def test_no_leftover_template_text(self):
        t = hwpx_io.para_text(build(load('yoji_law.json')))
        for s in ['점심메뉴', '제2조 정의', '대한석탄공사', '2026 3. 27.', '춘(春)']:
            self.assertNotIn(s, t)

    def test_missing_title(self):
        s = load('yoji_event.json')
        del s['title']
        with self.assertRaisesRegex(ValueError, 'title'):
            build(s)


if __name__ == '__main__':
    unittest.main()
