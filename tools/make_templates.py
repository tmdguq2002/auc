"""업로드된 실제 문서에서 개인정보·문서고유값을 지워 스킬용 서식 HWPX를 만든다.

사용: python3 tools/make_templates.py <원본.hwpx> <서식.hwpx> --kind gongmun|report
스킬 ZIP에는 포함하지 않는다.
"""
import argparse
import re
import struct
import zipfile
import zlib

PHONE = re.compile(r'\b0\d{1,2}-\d{3,4}-\d{4}\b')
EMAIL = re.compile(r'[A-Za-z0-9._-]+@auc\.or\.kr')

REPLACE = {
    'gongmun': [
        ('<hp:t>안전감사팀-85</hp:t>', '<hp:t>○○팀-○○</hp:t>'),
        ('<hp:t>2026.01.05.</hp:t>', '<hp:t></hp:t>'),
    ],
    'report': [
        ('<hp:t>전략기획부-4953</hp:t>', '<hp:t>○○부-○○</hp:t>'),
        ('<hp:t>2026. 10. 26.</hp:t>', '<hp:t></hp:t>'),
    ],
}
NAMES = ['이 주 민', '서동선', '권승협', '강주호', '최재형', '김창식', '전영민', '이강민']
PHOTO_IMAGES = ['image1', 'image2', 'image3', 'image4']


def blank_png(w=1, h=1):
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    raw = b''.join(b'\x00' + b'\xff\xff\xff' * w for _ in range(h))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def scrub(text, kind):
    for old, new in REPLACE[kind]:
        text = text.replace(old, new)
    for n in NAMES:
        text = text.replace('<hp:t>%s</hp:t>' % n, '<hp:t>○○○</hp:t>')
    text = PHONE.sub('031-389-○○○○', text)
    text = EMAIL.sub('○○○@auc.or.kr', text)
    return text


def preview_text(section_xml):
    texts = re.findall(r'<hp:t>([^<]*)</hp:t>', section_xml)
    return '\r\n'.join(t for t in texts if t.strip())[:1024]


def make(src, dst, kind):
    with zipfile.ZipFile(src) as zin:
        items = [(i.filename, zin.read(i.filename)) for i in zin.infolist()]
    out = []
    section = ''
    for name, data in items:
        if kind == 'report' and any(name == 'BinData/%s.jpg' % i for i in PHOTO_IMAGES):
            continue
        if name.endswith(('.xml', '.hpf', '.txt', '.rdf')):
            text = scrub(data.decode('utf-8'), kind)
            if kind == 'report' and name == 'Contents/header.xml':
                # 사진대지 칸 배경 사진 제거 -> 빈 칸
                text = re.sub(r'<hc:fillBrush><hc:imgBrush mode="TOTAL"><hc:img binaryItemIDRef="image[1-4]"[^>]*/></hc:imgBrush></hc:fillBrush>', '', text)
            if kind == 'report' and name == 'Contents/content.hpf':
                text = re.sub(r'<opf:item id="image[1-4]"[^>]*/>', '', text)
            if name == 'Contents/section0.xml':
                section = text
            data = text.encode('utf-8')
        if name == 'Preview/PrvImage.png':
            data = blank_png()
        out.append((name, data))
    with zipfile.ZipFile(dst, 'w') as zout:
        for name, data in out:
            if name == 'Preview/PrvText.txt':
                data = preview_text(section).encode('utf-8')
            ctype = zipfile.ZIP_STORED if name in ('mimetype', 'version.xml') or name.endswith('.png') else zipfile.ZIP_DEFLATED
            zout.writestr(zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)), data, compress_type=ctype)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--kind', choices=['gongmun', 'report'], required=True)
    a = ap.parse_args()
    make(a.src, a.dst, a.kind)
