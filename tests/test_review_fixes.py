"""최종 리뷰에서 나온 문제들의 회귀 테스트."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'skill', 'auc-docs', 'scripts')
sys.path.insert(0, SCRIPTS)
import build_hwpx  # noqa: E402
import hwpx_io  # noqa: E402
from check_privacy import check, find_personal_info  # noqa: E402


def fixture(name):
    with open(os.path.join(ROOT, 'tests', 'fixtures', name), encoding='utf-8') as f:
        return json.load(f)


def build(spec):
    out = os.path.join(tempfile.mkdtemp(), 'o.hwpx')
    build_hwpx.build(spec, out)
    return out


class PrivacyGaps(unittest.TestCase):
    def test_schedule_line_is_checked(self):
        spec = fixture('report_tft.json')
        spec['sections'][-1]['blocks'].append({'circle': '담당자 연락 010-1234-5678', 'when': '11월'})
        self.assertTrue(check(build(spec)))

    def test_more_phone_formats(self):
        for s in ['(031)389-5354', '01012345678', '+82-10-1234-5678', '031.389.5354']:
            self.assertTrue(find_personal_info(s), s)

    def test_names_without_colon_and_lists(self):
        for s in ['담당자 홍길동(☎ 내선)', '참석자: 홍길동, 김철수']:
            self.assertTrue(find_personal_info(s), s)

    def test_name_split_by_emphasis(self):
        spec = fixture('gongmun_futsal.json')
        spec['body'][0]['text'] = [['담당자: ', False], ['홍길동', True]]
        out = build(spec)
        self.assertTrue(check(out))
        d = tempfile.mkdtemp()
        js = os.path.join(d, 's.json')
        with open(js, 'w', encoding='utf-8') as f:
            json.dump(spec, f, ensure_ascii=False)
        self.assertTrue(check(js))

    def test_name_column_header_variants(self):
        for header in ['성명(서명)', '참석자']:
            spec = fixture('report_tft.json')
            spec['sections'][0]['blocks'][3]['table'] = {'header': ['부 서', header], 'rows': [['전략기획부', '홍길동']]}
            self.assertTrue(check(build(spec)), header)

    def test_no_false_positive_on_departments(self):
        for s in ['연락처: 안전감사팀', '담당자: 안전감사팀장', '작성자: 전략기획부', '이름: 미정',
                  '담당자 교육 실시', '담당자 지정']:
            self.assertEqual(find_personal_info(s), [], s)


class BuildRobustness(unittest.TestCase):
    def test_control_chars_stripped(self):
        spec = fixture('gongmun_futsal.json')
        spec['title'] = '제목\x0c테스트\x0b'
        out = build(spec)
        self.assertIn('제목테스트', hwpx_io.para_text(hwpx_io.read_section(out)[1]))

    def test_invalid_output_not_left_behind(self):
        out = os.path.join(tempfile.mkdtemp(), 'o.hwpx')
        spec = fixture('gongmun_futsal.json')
        spec['type'] = 'nope'
        with self.assertRaises(ValueError):
            build_hwpx.build(spec, out)
        self.assertFalse(os.path.exists(out))

    def test_empty_cells_keep_a_run(self):
        xml = hwpx_io.read_section(build(fixture('report_tft.json')))[1]
        self.assertNotRegex(xml, r'<hp:p [^>]*></hp:p>')
        xml = hwpx_io.read_section(build(fixture('gongmun_futsal.json')))[1]
        self.assertNotRegex(xml, r'<hp:p [^>]*></hp:p>')

    def test_empty_box_rejected(self):
        spec = fixture('gongmun_futsal.json')
        spec['body'][2]['box']['items'] = []
        with self.assertRaises(ValueError):
            build(spec)

    def test_text_as_string_and_box_emphasis(self):
        spec = fixture('gongmun_futsal.json')
        spec['body'][0]['text'] = '문자열 본문입니다.'
        spec['body'][2]['box']['items'] = [[['강조 항목', True]], '일반 항목']
        xml = hwpx_io.read_section(build(spec))[1]
        self.assertIn('1. 문자열 본문입니다.', hwpx_io.para_text(xml))
        self.assertIn('<hp:run charPrIDRef="22"><hp:t>강조 항목</hp:t></hp:run>', xml)

    def test_number_in_table_cell(self):
        spec = fixture('report_tft.json')
        spec['sections'][0]['blocks'][3]['table'] = {'header': ['구분', '인원'], 'rows': [['직원', 3]]}
        self.assertIn('3', hwpx_io.para_text(hwpx_io.read_section(build(spec))[1]))

    def test_too_many_subs_clear_error(self):
        spec = fixture('gongmun_one_item.json')
        spec['body'][0]['sub'] = [{'text': 'x'}] * 15
        with self.assertRaisesRegex(ValueError, '하위 항목'):
            build(spec)

    def test_missing_required_clear_error(self):
        for key in ('purpose', 'dept', 'title'):
            spec = fixture('report_tft.json')
            del spec[key]
            with self.assertRaisesRegex(ValueError, key):
                build(spec)

    def test_schedule_keeps_emphasis(self):
        spec = fixture('report_tft.json')
        spec['sections'][-1]['blocks'] = [{'circle': [['핵심', True], [' 일정', False]], 'when': '11월'}]
        self.assertIn('<hp:run charPrIDRef="16"><hp:t>핵심</hp:t></hp:run>', hwpx_io.read_section(build(spec))[1])

    def test_attachment_copy_count(self):
        spec = fixture('gongmun_one_item.json')
        spec['attachments'] = ['점검표 2부', '사진']
        text = hwpx_io.para_text(hwpx_io.read_section(build(spec))[1])
        self.assertIn('1. 점검표 2부.', text)
        self.assertNotIn('2부 1부', text)
        self.assertIn('2. 사진 1부.  끝.', text)


if __name__ == '__main__':
    unittest.main()
