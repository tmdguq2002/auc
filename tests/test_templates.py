import os
import re
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, 'skill', 'auc-docs', 'templates')

FORBIDDEN = [
    'shkwon@', '031-389-5354', '031-389-5249', '안전감사팀-85', '전략기획부-4953',
    '이 주 민', '서동선', '권승협', '강주호', '최재형', '김창식', '전영민', '이강민',
]


def all_text(path):
    out = []
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith(('.xml', '.hpf', '.txt', '.rdf')):
                out.append(z.read(name).decode('utf-8'))
    return '\n'.join(out)


class TemplateTest(unittest.TestCase):
    def test_templates_have_no_personal_info(self):
        for kind in ('gongmun', 'report', 'yoji'):
            text = all_text(os.path.join(TEMPLATES, kind + '.hwpx'))
            for s in FORBIDDEN:
                self.assertNotIn(s, text, '%s: %s' % (kind, s))
            self.assertIsNone(re.search(r'\b0\d{1,2}-\d{3,4}-\d{4}\b', text), kind)

    def test_template_size(self):
        for kind in ('report', 'yoji'):
            self.assertLess(os.path.getsize(os.path.join(TEMPLATES, kind + '.hwpx')), 500 * 1024, kind)

    def test_yoji_photos_removed_consistently(self):
        with zipfile.ZipFile(os.path.join(TEMPLATES, 'yoji.hwpx')) as z:
            names = z.namelist()
            xml = z.read('Contents/section0.xml').decode('utf-8')
            for ref in set(re.findall(r'binaryItemIDRef="(\w+)"', xml + z.read('Contents/header.xml').decode('utf-8'))):
                self.assertTrue(any(n.startswith('BinData/%s.' % ref) for n in names), ref)
        self.assertFalse(any(n.startswith('BinData/image3') or n.startswith('BinData/image4') for n in names))

    def test_templates_open_as_zip(self):
        for kind in ('gongmun', 'report', 'yoji'):
            with zipfile.ZipFile(os.path.join(TEMPLATES, kind + '.hwpx')) as z:
                first = z.infolist()[0]
                self.assertEqual(first.filename, 'mimetype')
                self.assertEqual(first.compress_type, zipfile.ZIP_STORED)
                self.assertEqual(z.read('mimetype'), b'application/hwp+zip')
                for name in z.namelist():
                    if name.startswith('BinData/'):
                        self.assertIn(name, z.read('Contents/content.hpf').decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
