"""HWPX 읽기·쓰기와 원형 문단 복제.

ElementTree로 다시 쓰면 네임스페이스 접두어가 바뀌어 한글 호환이 불안하므로
섹션 XML은 문자열 그대로 다루고, 바꾸는 부분만 잘라 붙인다.
"""
import os
import re
import xml.dom.minidom
import zipfile
from xml.sax.saxutils import escape, unescape  # noqa: F401 (다른 모듈에서 사용)

SECTION = 'Contents/section0.xml'
_TAG = re.compile(r'<hp:p\b[^>]*>|</hp:p>')
_CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')  # XML에 넣을 수 없는 제어문자(PDF 복사 시 섞임)


def read_section(path):
    with zipfile.ZipFile(path) as z:
        entries = {i.filename: z.read(i.filename) for i in z.infolist()}
    return entries, entries[SECTION].decode('utf-8')


def write_hwpx(path, entries, section_xml):
    """임시 파일에 쓰고 XML이 올바른지 확인한 뒤에만 path로 옮긴다."""
    section_xml = unique_object_ids(section_xml)
    xml.dom.minidom.parseString(section_xml.encode('utf-8'))
    tmp = path + '.tmp'
    with zipfile.ZipFile(tmp, 'w') as z:
        for name, data in entries.items():
            if name == SECTION:
                data = section_xml.encode('utf-8')
            elif name == 'Preview/PrvText.txt':
                data = preview_text(section_xml).encode('utf-8')
            stored = name in ('mimetype', 'version.xml') or name.endswith('.png')
            z.writestr(zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)), data,
                       compress_type=zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED)
    os.replace(tmp, path)


def split_section(xml):
    """섹션을 (머리, 최상위 문단 목록, 꼬리)로 나눈다. 표 안 문단은 바깥 문단에 포함."""
    paras, depth, start = [], 0, None
    first = last = None
    for m in _TAG.finditer(xml):
        if m.group().startswith('</'):
            depth -= 1
            if depth == 0:
                paras.append(xml[start:m.end()])
                last = m.end()
        else:
            if depth == 0:
                start = m.start()
                if first is None:
                    first = start
            depth += 1
    return xml[:first], paras, xml[last:]


def run_xml(char_pr, text):
    """글자 run. 빈 텍스트면 글자 모양만 가진 빈 run(서식의 빈 칸과 같은 형태)."""
    text = _CONTROL.sub('', str(text))
    if not text:
        return '<hp:run charPrIDRef="%s"/>' % char_pr
    return '<hp:run charPrIDRef="%s"><hp:t>%s</hp:t></hp:run>' % (char_pr, escape(text))


def clone_para(proto, runs, extra=''):
    """원형 문단의 여는 태그(문단 모양)를 유지하고 내용만 runs로 바꾼다.

    runs: [(charPrIDRef, 텍스트), ...]. extra는 마지막 run 뒤에 붙일 XML.
    줄 배치 정보(linesegarray)는 넣지 않아 한글이 다시 계산하게 한다.
    """
    open_tag = re.match(r'<hp:p\b[^>]*>', proto).group()
    return open_tag + ''.join(run_xml(c, t) for c, t in runs) + extra + '</hp:p>'


def para_text(xml):
    return ''.join(unescape(t) for t in re.findall(r'<hp:t>([^<]*)</hp:t>', xml))


def preview_text(section_xml):
    lines = []
    for p in split_section(section_xml)[1]:
        t = para_text(p).strip()
        if t:
            lines.append(t)
    return '\r\n'.join(lines)[:1024]


def _cell_span(xml, name):
    m = re.search(r'<hp:tc name="%s"' % re.escape(name), xml)
    if not m:
        raise KeyError('서식에 "%s" 칸이 없습니다' % name)
    return m.start(), xml.index('</hp:tc>', m.start())


def set_sublist_paras(xml, start, end, paras_xml):
    """xml[start:end] 안 첫 subList의 문단들을 paras_xml로 바꾼다."""
    s = xml.index('<hp:subList', start, end)
    s = xml.index('>', s) + 1
    e = xml.index('</hp:subList>', s, end)
    return xml[:s] + paras_xml + xml[e:]


def first_para_proto(xml_fragment):
    """조각 안 첫 문단의 여는 태그와 첫 run의 글자 모양 ID."""
    open_tag = re.search(r'<hp:p\b[^>]*>', xml_fragment).group()
    run = re.search(r'<hp:run charPrIDRef="(\d+)"', xml_fragment)
    return open_tag + '</hp:p>', run.group(1) if run else '0'


def set_cell(xml, name, text):
    """이름 붙은 표 칸(<hp:tc name=...>)의 내용을 text 한 문단으로 바꾼다."""
    start, end = _cell_span(xml, name)
    proto, char_pr = first_para_proto(xml[start:end])
    return set_sublist_paras(xml, start, end, clone_para(proto, [(char_pr, text)]))


def tc_spans(xml):
    """표 칸(<hp:tc>…</hp:tc>)들의 (시작, 끝) 위치. 칸 안에 표가 중첩되지 않은 서식 기준."""
    return [(m.start(), xml.index('</hp:tc>', m.start()) + len('</hp:tc>'))
            for m in re.finditer(r'<hp:tc\b', xml)]


def strip_linesegs(xml):
    return re.sub(r'<hp:linesegarray>.*?</hp:linesegarray>', '', xml)


def append_to_para(para, extra):
    """문단 끝(</hp:p> 앞)에 run XML을 덧붙인다."""
    assert para.endswith('</hp:p>')
    return para[:-len('</hp:p>')] + extra + '</hp:p>'


def unique_object_ids(xml):
    """복제로 겹친 표·그림 개체 id만 새 값으로 바꾼다(처음 나온 것은 유지)."""
    seen = set(re.findall(r'<hp:(?:tbl|pic|rect) id="(\d+)"', xml))
    counter = iter(range(1800000000, 2100000000))
    used = set()

    def fix(m):
        old = m.group(2)
        if old not in used:
            used.add(old)
            return m.group(0)
        new = next(i for i in counter if str(i) not in seen)
        return '<hp:%s id="%d"' % (m.group(1), new)
    return re.sub(r'<hp:(tbl|pic|rect) id="(\d+)"', fix, xml)
