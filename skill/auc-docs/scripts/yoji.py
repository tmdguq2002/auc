"""요지(한 장 요약) 생성: 머리(표어·날짜·부서) + 색 띠 + 제목 + 라벨 + 본문, 항상 한 쪽.

서식에는 참고용 요지 두 장이 들어 있다. 첫 장(글 위주, 줄간격 200%)과 둘째 장(표 위주, 160%)에서
원형 문단을 골라 쓴다(번호는 서식 문단 순번):
  0 머리(구역 설정 포함)   1 색 띠   2·4 빈 줄   3 제목   5 '개  요' 라벨
  6·10 ❍/- 항목(200%)   20·24 ❍/- 항목(160%, 표가 있으면)
  27 표(머리행·본문행)   13 사진 2칸 + 설명
"""
import re

import hwpx_io as h

CIRCLE = '❍'
NORMAL, EMPHASIS = '33', '34'
TABLE_WIDTH = 47612
PHOTO_HEIGHT, CAPTION_HEIGHT = 17673, 1848  # 원본 사진 높이, 설명 칸 높이
DEFAULT_LABEL = '개  요'


def _runs(prefix, value):
    if isinstance(value, str):
        value = [[value, False]]
    return [(NORMAL, prefix)] + [(EMPHASIS if em else NORMAL, t) for t, em in value]


def _header(proto, date, dept):
    p = h.strip_linesegs(proto)
    spans = h.tc_spans(p)
    out, last = [], 0
    for i, (s, e) in enumerate(spans):
        tc = p[s:e]
        if i in (1, 2):
            _, char_pr = h.first_para_proto(tc)
            tc = h.set_tc_text(tc, [(char_pr, date if i == 1 else dept)])
        out.append(p[last:s] + tc)
        last = e
    return ''.join(out) + p[last:]


def _photo(proto, captions):
    if isinstance(captions, str):
        captions = [captions]
    if len(captions) > 2:
        raise ValueError('사진 칸은 한 줄에 2개까지입니다')
    captions = list(captions) + [''] * (2 - len(captions))
    p = h.strip_linesegs(proto)
    spans = h.tc_spans(p)
    out, last = [], 0
    for i, (s, e) in enumerate(spans):
        tc = p[s:e]
        if i < 2:
            tc = h.set_tc_text(tc, [])  # 사진 자리: 빈 칸(사진을 붙일 수 있게 원본 사진 높이 유지)
            tc = re.sub(r'(<hp:cellSz width="\d+" height=")\d+', r'\g<1>%d' % PHOTO_HEIGHT, tc)
        else:
            tc = h.set_tc_text(tc, [('36', captions[i - 2])])
        out.append(p[last:s] + tc)
        last = e
    p = ''.join(out) + p[last:]
    return re.sub(r'(<hp:sz width="\d+" widthRelTo="ABSOLUTE" height=")\d+',
                  r'\g<1>%d' % (PHOTO_HEIGHT + CAPTION_HEIGHT), p, count=1)


def _page(P, page):
    for k in ('title', 'blocks'):
        if not page.get(k):
            raise ValueError('필수 항목이 없습니다: "%s"' % k)
    dense = any('table' in b for b in page['blocks'])
    circle, dash = (P['circle41'], P['dash41']) if dense else (P['circle39'], P['dash39'])
    label = h.strip_linesegs(P['label']).replace(
        '<hp:t>%s</hp:t>' % DEFAULT_LABEL, '<hp:t>%s</hp:t>' % h.escape(page.get('label') or DEFAULT_LABEL))

    out = [_header(P['head'], page.get('date', ''), page.get('dept', '')),
           h.strip_linesegs(P['bar']), P['blank_a'],
           h.clone_para(P['title'], [('30', page['title'])]), P['blank_b'], label]
    for b in page['blocks']:
        if 'circle' in b:
            out.append(h.clone_para(circle, _runs(' %s ' % CIRCLE, b['circle'])))
        elif 'dash' in b:
            out.append(h.clone_para(dash, _runs('  - ', b['dash'])))
        elif 'note' in b:
            out.append(h.clone_para(circle, _runs(' ※ ', b['note'])))
        elif 'table' in b:
            out.append(h.build_table(P['table'], b['table']['header'], b['table']['rows'], TABLE_WIDTH, '37', '38'))
        elif 'photo' in b:
            out.append(_photo(P['photo'], b['photo']))
        else:
            raise ValueError('알 수 없는 항목: %s' % list(b))
    return out


def build_yoji(spec, template, out):
    if 'pages' in spec:
        raise ValueError('요지는 한 장입니다. 주제가 여러 개면 요지를 따로 만드세요')
    entries, xml = h.read_section(template)
    head, ps, tail = h.split_section(xml)
    P = {k: ps[i] for k, i in dict(head=0, bar=1, blank_a=2, title=3, blank_b=4, label=5,
                                    circle39=6, dash39=10, photo=13,
                                    circle41=20, dash41=24, table=27).items()}
    h.write_hwpx(out, entries, head + ''.join(_page(P, spec)) + tail)
