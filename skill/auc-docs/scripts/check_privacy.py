"""결과물에 개인정보(전화·이메일·이름)가 남았는지 검사한다.

사용: python3 scripts/check_privacy.py <파일.hwpx|파일.json>
발견하면 목록을 출력하고 종료코드 1, 없으면 "개인정보 없음"과 종료코드 0.
자리표시(○○○, 031-389-○○○○, ○○○@auc.or.kr)와 부서·직위명은 통과한다.
"""
import json
import re
import sys
import zipfile
from xml.sax.saxutils import unescape

PHONE = re.compile(
    r'(?<![\d+])(?:\+82[-. ]?0?\d{1,2}|\(?0\d{1,2}\)?)[-. )]?\d{3,4}[-. ]\d{4}(?!\d)'
    r'|(?<!\d)01[016789]\d{7,8}(?!\d)')
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
LABEL = r'(?:성\s*명|이\s*름|담당자|작성자|기안자|참석자|연락처)'
NAME = r'([가-힣]{2,4})(?![가-힣])'
NAME_AFTER_COLON = re.compile(LABEL + r'\s*[:：]\s*' + NAME)
NAME_BEFORE_CONTACT = re.compile(LABEL + r'\s+' + NAME + r'\s*(?=[(（☎,/])')
NAME_HEADER = re.compile(r'성명|이름|참석자|담당자|작성자')
ORG_SUFFIX = re.compile(r'(팀|부|장|과|실|단|처|국|소|센터|본부)$')
NOT_NAMES = {'미정', '없음', '참조', '별도', '추후', '전원', '각자', '해당', '공란'}
PLACEHOLDER = re.compile(r'^[○\s]*$')


def _is_name(word):
    return not (word in NOT_NAMES or ORG_SUFFIX.search(word) or PLACEHOLDER.match(word))


def find_personal_info(text):
    found = [m.group() for m in PHONE.finditer(text)]
    found += [m.group() for m in EMAIL.finditer(text) if not m.group().startswith('○')]
    for rx in (NAME_AFTER_COLON, NAME_BEFORE_CONTACT):
        found += [m.group() for m in rx.finditer(text) if _is_name(m.group(1))]
    return found


def _name_column_values(rows):
    """표에서 머리칸이 성명·참석자 등인 열의 값 중 사람 이름으로 보이는 것."""
    if not rows:
        return []
    cols = [i for i, c in enumerate(rows[0]) if NAME_HEADER.search(re.sub(r'\s', '', str(c)))]
    vals = [str(r[i]).strip() for r in rows[1:] for i in cols if i < len(r)]
    return [v for v in vals if v and _is_name(re.sub(r'\s', '', v))]


def _xml_text(fragment):
    """XML 조각을 문단 단위 줄로. run이 나뉘어도(강조 등) 한 문단은 한 줄로 합친다."""
    lines, cur = [], []
    for m in re.finditer(r'<hp:t>(.*?)</hp:t>|<hp:p\b[^>]*>|</hp:p>', fragment, re.S):
        if m.group(1) is not None:
            cur.append(unescape(re.sub(r'<[^>]+>', ' ', m.group(1))))
        else:
            if cur:
                lines.append(''.join(cur))
            cur = []
    if cur:
        lines.append(''.join(cur))
    return lines


def _hwpx_texts_and_tables(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read('Contents/section0.xml').decode('utf-8')
    tables = []
    for tbl in re.findall(r'<hp:tbl\b.*?</hp:tbl>', xml, re.S):
        tables.append([[' '.join(_xml_text(tc)) for tc in re.findall(r'<hp:tc\b.*?</hp:tc>', tr, re.S)]
                       for tr in re.findall(r'<hp:tr>(.*?)</hp:tr>', tbl, re.S)])
    return _xml_text(xml), tables


def _is_runs(v):
    return isinstance(v, list) and v and all(
        isinstance(x, list) and len(x) == 2 and isinstance(x[0], str) and isinstance(x[1], bool) for x in v)


def _json_texts_and_tables(path):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    texts, tables = [], []

    def walk(v):
        if isinstance(v, str):
            texts.append(v)
        elif _is_runs(v):
            texts.append(''.join(t for t, _ in v))
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            if 'header' in v and 'rows' in v:
                tables.append([v['header']] + v['rows'])
            for x in v.values():
                walk(x)
    walk(data)
    return texts, tables


def check(path):
    texts, tables = (_hwpx_texts_and_tables if path.endswith('.hwpx') else _json_texts_and_tables)(path)
    found = []
    for t in texts:
        found += find_personal_info(t)
    for rows in tables:
        found += _name_column_values(rows)
    return found


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    found = check(argv[1])
    if found:
        print('개인정보로 보이는 항목 %d개 — 자리표시로 바꾸세요:' % len(found))
        for f in found:
            print('  -', f)
        return 1
    print('개인정보 없음')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
