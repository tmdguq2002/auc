"""내부 보고서 B형(ESG경영확산협의회 결과보고 모양): 표지 구역 + 본문 구역.

section0: 표지(결재·협조란, 제목, 부서) + 본문 누름틀 시작
section1 최상위 문단 중 원형으로 쓰는 것(번호는 서식 문단 순번):
  0 머리(로고)   1 부제목   2 제목 + 요약 상자   3 제목 아래 빈 줄
  4 첫 대제목 표   6 대제목 사이 빈 줄   7 대제목 표
  8 □ 항목   21 [안건] 줄   15 - 항목   16 • 항목   23 1. 항목   33 ※ 항목
  11 표(머리칸·기관칸·명단칸)   40 사진대지 2×2 + 누름틀 끝
"""
import re
import zipfile

import hwpx_io as h

SECTION1 = 'Contents/section1.xml'
ROMAN = 'ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ'
NORMAL, BOLD = '2', '28'
TABLE_WIDTH = 45982
HEADING_MIN, HEADING_MAX = 14461, 41000  # 대제목 제목 칸 너비(원본 4글자 기준 ~ 쪽 너비)
MAX_APPROVERS, MAX_COOPERATORS = 4, 6


def _runs(value, normal=NORMAL, emphasis=BOLD):
    if isinstance(value, str):
        return [(normal, value)]
    return [(emphasis if em else normal, t) for t, em in value]


def _plain(value):
    return value if isinstance(value, str) else ''.join(t for t, _ in value)


def _title_runs(title):
    """제목: 강조 부분은 남색(38), 나머지는 검정(29)."""
    return _runs(title, '29', '38')


def _cell_texts(p, texts):
    """문단 안 표 칸들을 순서대로 texts[i] = runs(또는 None=그대로)로 채운다."""
    spans = h.tc_spans(p)
    out, last = [], 0
    for i, (s, e) in enumerate(spans):
        tc = p[s:e]
        if i < len(texts) and texts[i] is not None:
            tc = h.set_tc_text(tc, texts[i])
        out.append(p[last:s] + tc)
        last = e
    return ''.join(out) + p[last:]


def _title_box(proto, title, summary):
    p = h.strip_linesegs(proto)
    open_end = p.index('>') + 1
    table_run = p.rindex('<hp:run', 0, p.index('<hp:tbl'))
    runs = ''.join(h.run_xml(c, t) for c, t in _title_runs(title)) + h.run_xml('43', ' ')
    p = p[:open_end] + runs + p[table_run:]
    return _cell_texts(p, [[('41', ' ')] + _runs(summary, '41', '44')])


def _heading(proto, n, title):
    p = _cell_texts(h.strip_linesegs(proto), [[('32', ROMAN[n])], None, [('34', title)]])
    # 제목 칸을 제목 길이에 맞춰 넓혀 한 줄에 들어가게 한다(20pt ≈ 글자당 2000)
    return h.widen_cells(p, {2}, min(HEADING_MAX, max(HEADING_MIN, len(title) * 2050 + 600)))


def _table(proto, header, rows):
    p = h.strip_linesegs(proto)
    tcs = {re.search(r'colAddr="(\d+)" rowAddr="(\d+)"', p[s:e]).groups(): p[s:e] for s, e in h.tc_spans(p)}
    head = [tcs[('0', '0')]]
    # 첫 열: 기관칸(굵게·음영), 나머지: 명단칸. 첫 본문 행만 머리행 아래 이중선, 나머지 행은 가는 실선
    first = [tcs[('1', '1')], tcs[('2', '1')]]
    rest = [tcs[('1', '2')], tcs[('2', '3')]]
    return h.build_table(p, header, rows, TABLE_WIDTH, '58', '53', head_tcs=head, body_tcs=first, rest_tcs=rest)


def _cover(xml, spec):
    for name, value in [('문서번호', spec.get('doc_no', '○○부-○○')), ('결재완료일자', spec.get('date', '')),
                        ('공개여부', spec.get('disclosure', '공개')), ('기안부서', spec['dept'])]:
        xml = h.set_cell(xml, name, value)
    for prefix, names, n in [('직위.', spec.get('approvers', []), MAX_APPROVERS),
                             ('협조직위.', spec.get('cooperators', []), MAX_COOPERATORS)]:
        for i in range(n):
            xml = h.set_cell(xml, prefix + str(i + 1), names[i] if i < len(names) else '')
    # 제목 칸: 첫 문단(머리말·단 설정 조판 부호 + 부제목) + 제목 문단
    start, end = h._cell_span(xml, '결재제목')
    first, title = h.cell_paras(xml, start, end)[:2]
    paras = h.replace_para_text(first, [('46', spec['subtitle'])] if spec.get('subtitle') else [])
    paras += h.replace_para_text(title, _title_runs(spec['title']))
    return h.set_sublist_paras(xml, start, end, paras)


def _body(ps, spec):
    P = {k: ps[i] for k, i in dict(head=0, subtitle=1, titlebox=2, gap=3, heading_first=4, sep=6,
                                    heading=7, square=8, agenda=21, dash=15, bullet=16, num=23,
                                    note=33, table=11, photo=40).items()}
    field_end = re.search(r'<hp:ctrl><hp:fieldEnd[^>]*/></hp:ctrl>', P['photo']).group()
    photo = h.strip_linesegs(P['photo']).replace(field_end, '')

    out = [P['head']]
    if spec.get('subtitle'):
        out.append(h.clone_para(P['subtitle'], [('46', spec['subtitle'])]))
    out += [_title_box(P['titlebox'], spec['title'], spec['summary']), P['gap']]
    for n, sec in enumerate(spec['sections']):
        if n:
            out.append(P['sep'])
        out.append(_heading(P['heading_first'] if n == 0 else P['heading'], n, sec['title']))
        num = 0
        for b in sec['blocks']:
            if 'num' not in b:
                num = 0 if ('agenda' in b or 'square' in b) else num
            if 'square' in b:
                out.append(h.clone_para(P['square'], [(NORMAL, '  □ ')] + _runs(b['square'])))
            elif 'agenda' in b:
                out.append(h.clone_para(P['agenda'], [(NORMAL, '    ')] + _runs(b['agenda'], '55', '55')))
            elif 'dash' in b:
                out.append(h.clone_para(P['dash'], [(NORMAL, '     - ' if n < 2 else '    - ')] + _runs(b['dash'])))
            elif 'bullet' in b:
                out.append(h.clone_para(P['bullet'], [(NORMAL, '      • ')] + _runs(b['bullet'])))
            elif 'num' in b:
                num += 1
                out.append(h.clone_para(P['num'], [(NORMAL, '     %d. ' % num)] + _runs(b['num'])))
            elif 'note' in b:
                out.append(h.clone_para(P['note'], [('64', '     ※ ')] + _runs(b['note'], '64', BOLD)))
            elif 'table' in b:
                out.append(_table(P['table'], b['table']['header'], b['table']['rows']))
            elif 'photo' in b:
                out.append(photo)
            else:
                raise ValueError('알 수 없는 항목: %s' % list(b))
    out[-1] = h.append_to_para(out[-1], '<hp:run charPrIDRef="%s">%s</hp:run>' % (NORMAL, field_end))
    return out


def build_report_b(spec, template, out):
    for k in ('title', 'dept', 'summary', 'sections'):
        if not spec.get(k):
            raise ValueError('필수 항목이 없습니다: "%s"' % k)
    if len(spec.get('approvers', [])) > MAX_APPROVERS:
        raise ValueError('결재란은 최대 %d칸입니다' % MAX_APPROVERS)
    if len(spec.get('cooperators', [])) > MAX_COOPERATORS:
        raise ValueError('협조란은 최대 %d칸입니다' % MAX_COOPERATORS)
    if len(spec['sections']) > len(ROMAN):
        raise ValueError('대제목은 최대 %d개입니다' % len(ROMAN))

    entries, cover = h.read_section(template)
    with zipfile.ZipFile(template) as z:
        body = z.read(SECTION1).decode('utf-8')
    head, ps, tail = h.split_section(body)
    h.write_hwpx(out, entries, _cover(cover, spec), {SECTION1: head + ''.join(_body(ps, spec)) + tail})
