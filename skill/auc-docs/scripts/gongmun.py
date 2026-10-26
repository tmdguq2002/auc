"""공문서(시행문) 생성: 서식의 원형 문단을 복제해 본문·머리·꼬리를 채운다.

서식 최상위 문단 구성:
  0 머리 표 + 본문 첫 줄(누름틀 시작)   1 본문 중간 줄
  2 박스 표                             3 본문 마지막 줄(누름틀 끝)
  4 꼬리 표(발신명의·결재·시행·연락처)
"""
import re

import hwpx_io as h

NORMAL, EMPHASIS = '7', '22'
BODY_PARA = '28'  # 본문 문단 모양(번호 '1.'에 맞춘 내어쓰기)
SUB_LABELS = [
    lambda i: '가나다라마바사아자차카타파하'[i] + '.',
    lambda i: '%d)' % (i + 1),
    lambda i: '가나다라마바사아자차카타파하'[i] + ')',
    lambda i: '(%d)' % (i + 1),
    lambda i: '(' + '가나다라마바사아자차카타파하'[i] + ')',
]
MAX_APPROVERS, MAX_COOPERATORS = 4, 3


def _runs(text):
    """문자열 또는 [[문구, 강조여부], ...]."""
    if isinstance(text, str):
        return [(NORMAL, text)]
    return [(EMPHASIS if em else NORMAL, t) for t, em in text]


def _required(spec, *keys):
    for k in keys:
        if not spec.get(k):
            raise ValueError('필수 항목이 없습니다: "%s"' % k)


def _numbered(spec):
    """편람: 본문이 한 항목뿐이면(하위 항목 없이) 번호를 붙이지 않는다."""
    texts = [b for b in spec['body'] if 'box' not in b]
    return not (len(texts) == 1 and not texts[0].get('sub'))


def _add_flat_body_style(header_xml):
    """본문 문단 모양(28)을 복사해 내어쓰기를 없앤 문단 모양을 새로 넣고 그 id를 돌려준다."""
    ids = [int(i) for i in re.findall(r'<hh:paraPr id="(\d+)"', header_xml)]
    new_id = max(ids) + 1
    pr = re.search(r'<hh:paraPr id="%s" .*?</hh:paraPr>' % BODY_PARA, header_xml, re.S).group()
    pr = pr.replace('<hh:paraPr id="%s" ' % BODY_PARA, '<hh:paraPr id="%d" ' % new_id, 1)
    pr = re.sub(r'<hc:intent value="-?\d+"', '<hc:intent value="0"', pr)
    end = header_xml.index('</hh:paraProperties>')
    header_xml = header_xml[:end] + pr + header_xml[end:]
    header_xml = re.sub(r'<hh:paraProperties itemCnt="\d+"', '<hh:paraProperties itemCnt="%d"' % (len(ids) + 1), header_xml)
    return header_xml, str(new_id)


def _lines(spec):
    """본문을 ('para', runs) / ('box', title, items) 목록으로 펼친다."""
    lines, n = [], 0

    def subs(items, level):
        if items and level >= len(SUB_LABELS):
            raise ValueError('하위 항목은 %d단계까지입니다' % len(SUB_LABELS))
        if len(items) > 14:
            raise ValueError('하위 항목은 한 단계에 14개까지입니다(가~하)')
        for i, it in enumerate(items):
            label = '  ' * (level + 1) + SUB_LABELS[level](i) + ' '
            lines.append(('para', [(NORMAL, label)] + _runs(it['text'])))
            subs(it.get('sub', []), level + 1)

    numbered = _numbered(spec)
    for block in spec['body']:
        if 'box' in block:
            if not block['box'].get('items'):
                raise ValueError('박스에 항목이 없습니다')
            lines.append(('box', block['box']['title'], block['box']['items']))
            continue
        n += 1
        label = [(NORMAL, '%d. ' % n)] if numbered else []
        lines.append(('para', label + _runs(block['text'])))
        subs(block.get('sub', []), 0)

    att = spec.get('attachments') or []
    for i, name in enumerate(att):
        if len(att) == 1:
            label = '붙임  '
        else:
            label = ('붙임  ' if i == 0 else '      ') + '%d. ' % (i + 1)
        name = name.strip().rstrip('.')
        if not re.search(r'\d+\s*부$', name):  # "점검표 2부"처럼 부수를 적었으면 그대로
            name += ' 1부'
        lines.append(('para', [(NORMAL, '%s%s.' % (label, name))]))

    if lines and lines[-1][0] == 'para':
        lines[-1][1].append((NORMAL, '  끝.'))
    else:
        lines.append(('para', [(NORMAL, '끝.')]))
    if lines[0][0] != 'para':
        raise ValueError('본문 첫 항목은 박스가 아닌 문장이어야 합니다')
    return lines


def _merge(runs):
    out = []
    for c, t in runs:
        if out and out[-1][0] == c:
            out[-1] = (c, out[-1][1] + t)
        else:
            out.append((c, t))
    return out


def _box(proto, title, items):
    x = proto.replace('&lt;주요 점검 사항&gt;', h.escape('<%s>' % title))
    # 항목 칸 = 맨 아래 가로 전체(colSpan=3) 칸. cellAddr는 칸 내용 뒤에 오므로 위치로 찾지 않는다.
    start, end = next((s, e) for s, e in h.tc_spans(x) if 'colSpan="3"' in x[s:e])
    p_proto, _ = h.first_para_proto(x[start:end])
    x = h.set_sublist_paras(x, start, end, ''.join(h.clone_para(p_proto, _runs(it)) for it in items))
    # 항목 수에 맞춰 칸·표 높이 조정(원본: 3항목 6171)
    new_h = max(1, len(items)) * 6171 // 3
    x = x.replace('<hp:cellSz width="47342" height="6171"/>', '<hp:cellSz width="47342" height="%d"/>' % new_h)
    x = x.replace('height="9135" heightRelTo', 'height="%d" heightRelTo' % (9135 - 6171 + new_h))
    return re.sub(r'<hp:linesegarray>.*?</hp:linesegarray>', '', x)


def build_gongmun(spec, template, out):
    _required(spec, 'title', 'body')
    if len(spec.get('approvers', [])) > MAX_APPROVERS:
        raise ValueError('결재란은 최대 %d칸입니다' % MAX_APPROVERS)
    if len(spec.get('cooperators', [])) > MAX_COOPERATORS:
        raise ValueError('협조란은 최대 %d칸입니다' % MAX_COOPERATORS)

    entries, xml = h.read_section(template)
    head, paras, tail = h.split_section(xml)
    p_first, p_mid, p_box, p_last, p_foot = paras
    field_end = re.search(r'<hp:ctrl><hp:fieldEnd[^>]*/></hp:ctrl>', p_last).group()
    end_run = '<hp:run charPrIDRef="%s">%s</hp:run>' % (NORMAL, field_end)

    lines = _lines(spec)
    rendered = []
    for i, line in enumerate(lines):
        extra = end_run if i == len(lines) - 1 else ''
        if i == 0:
            runs = _merge(line[1])
            if runs[0][0] != NORMAL:  # 서식의 첫 run은 일반 글자 모양이라, 강조로 시작하면 빈 일반 run을 앞에 둔다
                runs.insert(0, (NORMAL, ''))
            # 첫 줄은 머리 표·누름틀 시작과 같은 run 안에서 이어진다
            cut = p_first.index('</hp:fieldBegin></hp:ctrl>') + len('</hp:fieldBegin></hp:ctrl>')
            first = p_first[:cut] + '<hp:t>%s</hp:t></hp:run>' % h.escape(runs[0][1])
            first += ''.join(h.run_xml(c, t) for c, t in runs[1:]) + extra + '</hp:p>'
            rendered.append(first)
        elif line[0] == 'para':
            rendered.append(h.clone_para(p_mid, _merge(line[1]), extra))
        else:
            box = _box(p_box, line[1], line[2])
            if extra:
                box = box[:-len('</hp:p>')] + extra + '</hp:p>'
            rendered.append(box)
    if not _numbered(spec):
        # 번호 없는 한 문단: 내어쓰기 없는 문단 모양으로 바꾼다(박스 등 표 안 문단은 그대로)
        header_xml, flat = _add_flat_body_style(entries['Contents/header.xml'].decode('utf-8'))
        entries = dict(entries, **{'Contents/header.xml': header_xml.encode('utf-8')})
        tag = 'paraPrIDRef="%s"' % BODY_PARA
        rendered = [p.replace(tag, 'paraPrIDRef="%s"' % flat, 1) if tag in p[:p.index('>')] else p
                    for p in rendered]

    head_xml = rendered[0]
    head_xml = h.set_cell(head_xml, '수신', spec.get('receiver', '수신자참조'))
    head_xml = h.set_cell(head_xml, '경유', spec.get('via', ''))
    head_xml = h.set_cell(head_xml, '결재제목', spec['title'])
    rendered[0] = head_xml

    foot = p_foot
    foot = h.set_cell(foot, '발신명의', spec.get('sender') or '안양도시공사사장')
    foot = h.set_cell(foot, '각안수신처', ', '.join(spec.get('receivers', [])))
    for i in range(MAX_APPROVERS):
        names = spec.get('approvers', [])
        foot = h.set_cell(foot, '직위.%d' % (i + 1), names[i] if i < len(names) else '')
    for i in range(MAX_COOPERATORS):
        names = spec.get('cooperators', [])
        foot = h.set_cell(foot, '협조직위.%d' % (i + 1), names[i] if i < len(names) else '')
    foot = h.set_cell(foot, '문서번호', spec.get('doc_no', '○○팀-○○'))
    foot = h.set_cell(foot, '시행일자', spec.get('date', ''))
    foot = h.set_cell(foot, '공개여부', spec.get('disclosure', '공개'))

    h.write_hwpx(out, entries, head + ''.join(rendered) + foot + tail)
