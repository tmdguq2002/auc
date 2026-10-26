import os
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'skill', 'auc-docs', 'scripts'))
import hwpx_io  # noqa: E402

GONGMUN = os.path.join(ROOT, 'skill', 'auc-docs', 'templates', 'gongmun.hwpx')


class HwpxIoTest(unittest.TestCase):
    def test_roundtrip(self):
        entries, xml = hwpx_io.read_section(GONGMUN)
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'o.hwpx')
            hwpx_io.write_hwpx(out, entries, xml)
            entries2, xml2 = hwpx_io.read_section(out)
            self.assertEqual(xml, xml2)
            with zipfile.ZipFile(out) as z:
                self.assertEqual(z.infolist()[0].filename, 'mimetype')
                self.assertEqual(z.infolist()[0].compress_type, zipfile.ZIP_STORED)

    def test_split_top_level(self):
        _, xml = hwpx_io.read_section(GONGMUN)
        head, paras, tail = hwpx_io.split_section(xml)
        self.assertEqual(len(paras), 5)
        self.assertEqual(head + ''.join(paras) + tail, xml)

    def test_clone_escapes(self):
        _, xml = hwpx_io.read_section(GONGMUN)
        proto = hwpx_io.split_section(xml)[1][1]
        out = hwpx_io.clone_para(proto, [(7, '<주요> & "x"')])
        self.assertIn('&lt;주요&gt; &amp;', out)
        self.assertNotIn('linesegarray', out)
        self.assertIn('paraPrIDRef="28"', out)
        self.assertEqual(hwpx_io.para_text(out), '<주요> & "x"')

    def test_write_updates_preview(self):
        entries, xml = hwpx_io.read_section(GONGMUN)
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'o.hwpx')
            hwpx_io.write_hwpx(out, entries, xml.replace('풋살장', '테니스장'))
            with zipfile.ZipFile(out) as z:
                self.assertIn('테니스장', z.read('Preview/PrvText.txt').decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
