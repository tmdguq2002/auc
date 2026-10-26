import json
import os
import re
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'skill', 'auc-docs', 'scripts'))
import build_hwpx  # noqa: E402
import hwpx_io  # noqa: E402


def spec():
    with open(os.path.join(ROOT, 'tests', 'fixtures', 'report_b_esg.json'), encoding='utf-8') as f:
        return json.load(f)


def build(s):
    out = os.path.join(tempfile.mkdtemp(), 'o.hwpx')
    build_hwpx.build(s, out)
    with zipfile.ZipFile(out) as z:
        return z.read('Contents/section0.xml').decode('utf-8'), z.read('Contents/section1.xml').decode('utf-8')


def lines(xml):
    return [hwpx_io.para_text(p) for p in hwpx_io.split_section(xml)[1]]


class ReportBTest(unittest.TestCase):
    def test_cover(self):
        cover, _ = build(spec())
        t = hwpx_io.para_text(cover)
        for s in ['전략기획부-○○', '★담당자', '전략기획부장', '공개', '-공사·공단 협력 ESG경영 활성화를 위한-',
                  '제2회 ESG경영확산협의회 결과보고', '전략기획부']:
            self.assertIn(s, t)
        self.assertEqual(cover.count('<hp:fieldBegin'), 1)

    def test_cover_keeps_page_controls(self):
        with zipfile.ZipFile(os.path.join(ROOT, 'skill', 'auc-docs', 'templates', 'report_b.hwpx')) as z:
            tpl = z.read('Contents/section0.xml').decode('utf-8')
        for s in (spec(), dict(spec(), subtitle='')):
            cover, _ = build(s)
            for tag in ('<hp:header ', '<hp:colPr ', '<hp:secPr', '<hp:pageHiding'):
                self.assertEqual(tpl.count(tag), cover.count(tag), tag)

    def test_title_area(self):
        _, body = build(spec())
        t = lines(body)
        self.assertIn('-공사·공단 협력 ESG경영 활성화를 위한-', t)
        self.assertIn('<hp:run charPrIDRef="38"><hp:t>ESG경영확산협의회</hp:t></hp:run>', body)
        self.assertTrue(any(l.startswith('제2회 ESG경영확산협의회 결과보고') and '협의체를 구성' in l for l in t))
        self.assertIn('<hp:run charPrIDRef="44"><hp:t>ESG경영 협의체를 구성</hp:t></hp:run>', body)

    def test_headings(self):
        _, body = build(spec())
        heads = [l for l in lines(body) if re.match(r'^[ⅠⅡⅢⅣ]', l)]
        self.assertEqual(heads, ['Ⅰ관련근거', 'Ⅱ추진결과', 'Ⅲ향후일정', 'Ⅳ사진대지'])

    def test_long_heading_fits_one_line(self):
        s = spec()
        s['sections'][0]['title'] = '참여기관 만족도 조사 결과'
        _, body = build(s)
        head = [p for p in hwpx_io.split_section(body)[1] if '참여기관 만족도' in hwpx_io.para_text(p)][0]
        cells = re.findall(r'<hp:tc\b.*?</hp:tc>', head, re.S)
        widths = [int(re.search(r'<hp:cellSz width="(\d+)"', c).group(1)) for c in cells]
        self.assertGreaterEqual(widths[2], len('참여기관 만족도 조사 결과') * 2000)
        self.assertEqual(int(re.search(r'<hp:sz width="(\d+)"', head).group(1)), sum(widths))

    def test_blocks(self):
        t = lines(build(spec())[1])
        for s in ['  □ 전략기획부-4173(2026.9.7.) 「제1회 ESG경영확산협의회 결과보고」',
                  '  □ 일    시: 2026. 9. 15.(화) 13:30',
                  '    [안건1] 2027 경영평가 대응 「성과공유제」 부문 과제코칭',
                  '     - 성과공유제 제도 개정사항 안내',
                  '      • 신기술(정부인증) 제도만 과업연장 가능',
                  '     1. 금천 : 유아체육 프로그램 추진',
                  '     2. 구로 : 안전체험관 체험',
                  '     ※ 프로그램 운영 시 담당자 참석 & 참여자 관리',
                  '    - 일    자: 2026. 10월 중']:
            self.assertIn(s, t)

    def test_num_restarts_after_agenda(self):
        s = spec()
        blocks = s['sections'][1]['blocks']
        blocks.insert(5, {'num': '첫 안건 항목'})
        t = lines(build(s)[1])
        self.assertIn('     1. 첫 안건 항목', t)
        self.assertIn('     1. 금천 : 유아체육 프로그램 추진', t)

    def test_emphasis(self):
        _, body = build(spec())
        self.assertIn('<hp:run charPrIDRef="28"><hp:t>일    시</hp:t></hp:run>', body)
        self.assertIn('<hp:run charPrIDRef="55"><hp:t>[안건1] 2027 경영평가 대응 「성과공유제」 부문 과제코칭</hp:t></hp:run>', body)

    def test_table(self):
        _, body = build(spec())
        tbl = re.search(r'<hp:tbl\b(?:(?!</hp:tbl>).)*안양도시공사.*?</hp:tbl>', body, re.S).group()
        self.assertIn('rowCnt="3" colCnt="2"', tbl)
        self.assertNotIn('<hp:pic', tbl)
        self.assertNotIn('colSpan="2"', tbl)
        self.assertNotIn('rowSpan="4"', tbl)
        w = [int(x) for x in re.findall(r'<hp:cellSz width="(\d+)"', tbl)[:2]]
        self.assertEqual(sum(w), 45982)

    def test_table_rest_rows_use_plain_borders(self):
        s = spec()
        s['sections'][1]['blocks'][1]['table']['rows'] += [['군포도시공사', '○○○ 주임'], ['의왕도시공사', '○○○ 과장']]
        _, body = build(s)
        tbl = re.search(r'<hp:tbl\b(?:(?!</hp:tbl>).)*안양도시공사.*?</hp:tbl>', body, re.S).group()
        rows = re.findall(r'<hp:tr>(.*?)</hp:tr>', tbl, re.S)
        self.assertEqual(re.findall(r'borderFillIDRef="(\d+)"', rows[1]), ['31', '35'])  # 머리행 아래: 위 이중선
        for r in rows[2:]:
            self.assertEqual(re.findall(r'borderFillIDRef="(\d+)"', r), ['32', '29'])  # 나머지: 가는 실선

    def test_photo_and_field_end(self):
        _, body = build(spec())
        paras = hwpx_io.split_section(body)[1]
        self.assertEqual(body.count('<hp:fieldEnd'), 1)
        self.assertIn('<hp:fieldEnd', paras[-1])
        self.assertEqual(len(re.findall(r'<hp:tc\b', paras[-1])), 4)

    def test_field_end_without_photo(self):
        s = spec()
        s['sections'] = s['sections'][:3]
        _, body = build(s)
        self.assertEqual(body.count('<hp:fieldEnd'), 1)
        self.assertIn('<hp:fieldEnd', hwpx_io.split_section(body)[1][-1])

    def test_no_leftover_template_text(self):
        cover, body = build(spec())
        t = hwpx_io.para_text(cover + body)
        for s in ['빙상', '구로구시설관리공단 본사', '하임리히법', '참석자 명단', '광명 : ESG']:
            self.assertNotIn(s, t)

    def test_plain_title_and_no_subtitle(self):
        s = spec()
        s['title'] = '청렴 교육 결과보고'
        del s['subtitle']
        cover, body = build(s)
        self.assertIn('청렴 교육 결과보고', hwpx_io.para_text(cover))
        self.assertNotIn('-공사·공단 협력', hwpx_io.para_text(cover + body))

    def test_missing_required(self):
        for key in ('title', 'dept', 'summary', 'sections'):
            s = spec()
            del s[key]
            with self.assertRaisesRegex(ValueError, key):
                build(s)


if __name__ == '__main__':
    unittest.main()
