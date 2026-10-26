"""내부 보고서 생성: 표지 + 목적 + Ⅰ·Ⅱ… 대제목별 본문.

서식 최상위 문단 중 원형으로 쓰는 것(번호는 서식 문단 순번):
  0 표지(결재·협조란, 제목, 부서) + 본문 누름틀 시작
  1 제목·목적 박스   2 빈 줄   3 대제목 표   14 대제목 앞 빈 줄
  16 ' 1.' 소제목   4 동그라미   48 '-'   43 '※'   63 동그라미+일정(탭)
  7 표(머리행·본문행)   61 사진대지   66 마지막 문단(누름틀 끝)   21 소제목 앞 빈 줄
"""
import re

import hwpx_io as h

CIRCLE = ''
ROMAN = 'ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ'
MAX_APPROVERS, MAX_COOPERATORS = 4, 6
TABLE_WIDTH = 46216


def _runs(value, normal, emphasis):
    if isinstance(value, str):
        return [(normal, value)]
    return [(emphasis if em else normal, t) for t, em in value]


def _with_prefix(prefix, value, normal, emphasis):
    runs = _runs(value, normal, emphasis)
    return [(normal, prefix)] + runs


def _replace_text_runs(cell, runs):
    """칸 안 첫 문단에서 글자 run만 바꾸고 조판 부호(ctrl) run은 남긴다."""
    s = cell.index('<hp:p ')
    e = cell.index('</hp:p>', s) + len('</hp:p>')
    para = h.strip_linesegs(cell[s:e])
    kept = [r for r in re.findall(r'<hp:run\b[^>]*/>|<hp:run\b[^>]*>.*?</hp:run>', para, re.S)
            if '<hp:t' not in r and '<hp:ctrl>' in r]
    open_tag = re.match(r'<hp:p\b[^>]*>', para).group()
    new = open_tag + ''.join(kept) + ''.join(h.run_xml(c, t) for c, t in runs) + '</hp:p>'
    return cell[:s] + new + cell[e:]


def _heading(proto, n, title):
    p = h.strip_linesegs(proto)
    spans = h.tc_spans(p)
    out, last = [], 0
    for i, (s, e) in enumerate(spans):
        tc = p[s:e]
        if i == 0:
            tc = h.set_tc_text(tc, [('10', ROMAN[n])])
        elif i == 1:
            tc = h.set_tc_text(tc, [('11', title)])
        out.append(p[last:s] + tc)
        last = e
    return ''.join(out) + p[last:]


def _photo(proto, caption):
    p = h.strip_linesegs(proto)
    s, e = h.tc_spans(p)[-1]
    return p[:s] + h.set_tc_text(p[s:e], [('33', caption)]) + p[e:]


def _schedule(proto, text, when):
    """' ○ 내용 <탭> 일정' — 탭은 원형 문단의 점선 채움 탭을 그대로 쓴다."""
    tab = re.search(r'<hp:tab [^>]*/>', proto).group()
    open_tag = re.match(r'<hp:p\b[^>]*>', proto).group()
    runs = _with_prefix(' %s ' % CIRCLE, text, '12', '16')
    tail = '<hp:run charPrIDRef="12"><hp:t> %s %s</hp:t></hp:run>' % (tab, h.escape(when))
    return open_tag + ''.join(h.run_xml(c, t) for c, t in runs) + tail + '</hp:p>'


def build_report(spec, template, out):
    for k in ('title', 'dept', 'purpose', 'sections'):
        if not spec.get(k):
            raise ValueError('필수 항목이 없습니다: "%s"' % k)
    if len(spec.get('approvers', [])) > MAX_APPROVERS:
        raise ValueError('결재란은 최대 %d칸입니다' % MAX_APPROVERS)
    if len(spec.get('cooperators', [])) > MAX_COOPERATORS:
        raise ValueError('협조란은 최대 %d칸입니다' % MAX_COOPERATORS)
    if len(spec['sections']) > len(ROMAN):
        raise ValueError('대제목은 최대 %d개입니다' % len(ROMAN))

    entries, xml = h.read_section(template)
    head, ps, tail = h.split_section(xml)
    P = {k: ps[i] for k, i in dict(cover=0, intro=1, blank=2, heading=3, gap=14, num=16, circle=4,
                                    dash=48, note=43, schedule=63, table=7, photo=61, last=66,
                                    num_gap=21).items()}
    field_end = re.search(r'<hp:run charPrIDRef="\d+"><hp:ctrl><hp:fieldEnd[^>]*/></hp:ctrl><hp:t/></hp:run>',
                          P['last']).group()

    cover = P['cover']
    cover = h.set_cell(cover, '문서번호', spec.get('doc_no', '○○부-○○'))
    cover = h.set_cell(cover, '결재완료일자', spec.get('date', ''))
    cover = h.set_cell(cover, '공개여부', spec.get('disclosure', '공개'))
    for i in range(MAX_APPROVERS):
        names = spec.get('approvers', [])
        cover = h.set_cell(cover, '직위.%d' % (i + 1), names[i] if i < len(names) else '')
    for i in range(MAX_COOPERATORS):
        names = spec.get('cooperators', [])
        cover = h.set_cell(cover, '협조직위.%d' % (i + 1), names[i] if i < len(names) else '')
    cover = h.set_cell(cover, '결재제목', spec['title'])
    cover = h.set_cell(cover, '기안부서', spec['dept'])

    intro = h.strip_linesegs(P['intro'])
    spans = h.tc_spans(intro)
    (ts, te), (ps_, pe) = spans[3], spans[4]
    title_tc = _replace_text_runs(intro[ts:te], [('1', spec['title'])])
    purpose_tc = _replace_text_runs(intro[ps_:pe], [('7', ' ')] + _runs(spec['purpose'], '7', '37'))
    intro = intro[:ts] + title_tc + intro[te:ps_] + purpose_tc + intro[pe:]

    body = [cover, intro, P['blank']]
    for n, sec in enumerate(spec['sections']):
        if n:
            body.append(P['gap'])
        body.append(_heading(P['heading'], n, sec['title']))
        num = 0
        for b in sec['blocks']:
            if 'num' in b:
                num += 1
                if num > 1:  # 원본처럼 두 번째 소제목부터 앞에 빈 줄
                    body.append(P['num_gap'])
                body.append(h.clone_para(P['num'], _with_prefix(' %d. ' % num, b['num'], '19', '19')))
            elif 'circle' in b and b.get('when'):
                body.append(_schedule(P['schedule'], b['circle'], b['when']))
            elif 'circle' in b:
                body.append(h.clone_para(P['circle'], _with_prefix(' %s ' % CIRCLE, b['circle'], '12', '16')))
            elif 'dash' in b:
                body.append(h.clone_para(P['dash'], _with_prefix('  - ', b['dash'], '20', '16')))
            elif 'note' in b:
                body.append(h.clone_para(P['note'], _with_prefix('※ ', b['note'], '31', '31')))
            elif 'table' in b:
                body.append(h.build_table(P['table'], b['table']['header'], b['table']['rows'], TABLE_WIDTH, '14', '15'))
            elif 'photo' in b:
                body.append(_photo(P['photo'], b['photo']))
            else:
                raise ValueError('알 수 없는 항목: %s' % list(b))
    body[-1] = h.append_to_para(body[-1], field_end)
    h.write_hwpx(out, entries, head + ''.join(body) + tail)
