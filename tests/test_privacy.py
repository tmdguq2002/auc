import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'skill', 'auc-docs', 'scripts')
sys.path.insert(0, SCRIPTS)
from check_privacy import find_personal_info  # noqa: E402
import build_hwpx  # noqa: E402


class PrivacyTest(unittest.TestCase):
    def test_catches(self):
        for s in ['연락처 010-1234-5678', '전화 031-389-5354', 'shkwon@auc.or.kr 로 회신',
                  '담당자: 홍길동', '성명 : 김철수']:
            self.assertTrue(find_personal_info(s), s)

    def test_allows(self):
        for s in ['031-389-○○○○', '○○○@auc.or.kr', 'www.auc.or.kr', '13918 경기도 안양시',
                  '2026. 10. 22.(목)', '담당자: ○○○', '★담당자', '1,234,567원', '2026-10-22']:
            self.assertEqual(find_personal_info(s), [], s)

    def _report_with_name(self, name):
        with open(os.path.join(ROOT, 'tests', 'fixtures', 'report_tft.json'), encoding='utf-8') as f:
            spec = json.load(f)
        spec['sections'][0]['blocks'][3]['table']['rows'][0][2] = name
        d = tempfile.mkdtemp()
        js, hw = os.path.join(d, 'r.json'), os.path.join(d, 'r.hwpx')
        with open(js, 'w', encoding='utf-8') as f:
            json.dump(spec, f, ensure_ascii=False)
        build_hwpx.build(spec, hw)
        return js, hw

    def run_cli(self, path):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, 'check_privacy.py'), path],
                              capture_output=True, text=True)

    def test_name_column_in_table(self):
        for path in self._report_with_name('홍길동'):
            r = self.run_cli(path)
            self.assertEqual(r.returncode, 1, path)
            self.assertIn('홍길동', r.stdout)

    def test_clean_files(self):
        for path in self._report_with_name('○○○'):
            r = self.run_cli(path)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn('개인정보 없음', r.stdout)
        with open(os.path.join(ROOT, 'tests', 'fixtures', 'gongmun_futsal.json'), encoding='utf-8') as f:
            out = os.path.join(tempfile.mkdtemp(), 'g.hwpx')
            build_hwpx.build(json.load(f), out)
        r = self.run_cli(out)
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == '__main__':
    unittest.main()
