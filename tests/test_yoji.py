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


def spec():
    with open(os.path.join(ROOT, 'tests', 'fixtures', 'yoji_two_pages.json'), encoding='utf-8') as f:
        return json.load(f)


def build(s):
    out = os.path.join(tempfile.mkdtemp(), 'o.hwpx')
    build_hwpx.build(s, out)
    return hwpx_io.read_section(out)[1]


def texts(xml):
    return [hwpx_io.para_text(p) for p in hwpx_io.split_section(xml)[1]]


class YojiTest(unittest.TestCase):
    def test_two_pages(self):
        xml = build(spec())
        paras = hwpx_io.split_section(xml)[1]
        heads = [p for p in paras if '존중과 성장의 안양도시공사' in hwpx_io.para_text(p)]
        self.assertEqual(len(heads), 2)
        self.assertIn('pageBreak="1"', re.match(r'<hp:p\b[^>]*>', heads[1]).group())
        self.assertEqual(xml.count('<hp:secPr'), 1)
        for s in ['2026. 3. 27.(금)', '2026. 3. 30.(월)', '안전감사팀「춘(春)나게 소통」계획', '중대재해처벌법 개요 & 사례']:
            self.assertIn(s, hwpx_io.para_text(xml))

    def test_blocks(self):
        t = texts(build(spec()))
        self.assertIn(' ❍ 시    간 : 11:00 ~ 13:00', t)
        self.assertIn('  - 춘(春)나게 걷기 : 잣나무 숲까지 봄 향기를 맡으며 이동', t)
        self.assertIn(' ※ 법 시행 이후 처벌받은 공공기관장 없음', t)

    def test_emphasis(self):
        xml = build(spec())
        self.assertIn('<hp:run charPrIDRef="34"><hp:t>춘(春)나게 걷기</hp:t></hp:run>', xml)
        self.assertIn('<hp:run charPrIDRef="34"><hp:t>경영책임자</hp:t></hp:run>', xml)

    def test_labels(self):
        t = texts(build(spec()))
        self.assertIn('개  요', t)
        self.assertIn('현  황', t)

    def test_header_cells(self):
        xml = build(spec())
        head = [p for p in hwpx_io.split_section(xml)[1] if '존중과 성장' in hwpx_io.para_text(p)][0]
        cells = [hwpx_io.para_text(c) for c in re.findall(r'<hp:tc\b.*?</hp:tc>', head, re.S)]
        self.assertEqual(cells[1:], ['2026. 3. 27.(금)', '안전감사팀'])

    def test_table_and_photo(self):
        xml = build(spec())
        tbl = re.search(r'<hp:tbl\b(?:(?!</hp:tbl>).)*2022년 3월.*?</hp:tbl>', xml, re.S).group()
        self.assertIn('rowCnt="3" colCnt="2"', tbl)
        photo = [p for p in hwpx_io.split_section(xml)[1] if '도보 이동거리' in hwpx_io.para_text(p)][0]
        self.assertNotIn('<hp:pic', photo)
        self.assertIn('관악산 산림욕장(잣나무숲)', hwpx_io.para_text(photo))

    def test_photo_cells_keep_height(self):
        xml = build(spec())
        photo = [p for p in hwpx_io.split_section(xml)[1] if '도보 이동거리' in hwpx_io.para_text(p)][0]
        heights = [int(x) for x in re.findall(r'<hp:cellSz width="\d+" height="(\d+)"', photo)]
        self.assertGreaterEqual(min(heights[:2]), 16000)  # 원본 사진 높이 수준

    def test_table_columns_keep_own_alignment(self):
        xml = build(spec())
        tbl = re.search(r'<hp:tbl\b(?:(?!</hp:tbl>).)*2022년 3월.*?</hp:tbl>', xml, re.S).group()
        cells = re.findall(r'<hp:tc\b.*?</hp:tc>', tbl, re.S)
        body = {re.search(r'colAddr="(\d+)" rowAddr="(\d+)"', c).groups(): re.search(r'paraPrIDRef="(\d+)"', c).group(1) for c in cells}
        self.assertEqual(body[('0', '1')], '40')  # 일자: 가운데
        self.assertEqual(body[('1', '1')], '43')  # 개요: 원본 둘째 열 문단 모양

    def test_line_spacing_by_page(self):
        paras = hwpx_io.split_section(build(spec()))[1]
        p1 = [p for p in paras if hwpx_io.para_text(p).startswith(' ❍ 시')][0]
        p2 = [p for p in paras if hwpx_io.para_text(p).startswith(' ❍ 처벌대상')][0]
        self.assertIn('paraPrIDRef="39"', p1)  # 표 없는 쪽: 줄간격 200%
        self.assertIn('paraPrIDRef="41"', p2)  # 표 있는 쪽: 160%

    def test_single_page_shorthand(self):
        page = spec()['pages'][0]
        page['type'] = 'yoji'
        self.assertIn('춘(春)나게 소통', hwpx_io.para_text(build(page)))

    def test_no_leftover_template_text(self):
        t = hwpx_io.para_text(build(spec()))
        for s in ['점심메뉴', '제2조 정의', '대한석탄공사', '2026 3. 27.']:
            self.assertNotIn(s, t)

    def test_missing_title(self):
        s = spec()
        del s['pages'][1]['title']
        with self.assertRaisesRegex(ValueError, 'title'):
            build(s)


if __name__ == '__main__':
    unittest.main()
