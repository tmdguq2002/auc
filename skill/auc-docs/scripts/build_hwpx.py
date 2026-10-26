"""JSON 내용으로 안양도시공사 서식 HWPX를 만든다.

사용: python3 scripts/build_hwpx.py <내용.json> <결과.hwpx>
JSON의 "type": "gongmun"(공문서) | "report"(내부 보고서, "style": "b"면 B형) | "yoji"(요지)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')


def build(spec, out):
    kind = spec.get('type')
    if kind == 'gongmun':
        from gongmun import build_gongmun
        build_gongmun(spec, os.path.join(TEMPLATES, 'gongmun.hwpx'), out)
    elif kind == 'report' and spec.get('style') == 'b':
        from report_b import build_report_b
        build_report_b(spec, os.path.join(TEMPLATES, 'report_b.hwpx'), out)
    elif kind == 'report':
        from report import build_report
        build_report(spec, os.path.join(TEMPLATES, 'report.hwpx'), out)
    elif kind == 'yoji':
        from yoji import build_yoji
        build_yoji(spec, os.path.join(TEMPLATES, 'yoji.hwpx'), out)
    else:
        raise ValueError('"type"은 gongmun, report, yoji 중 하나여야 합니다: %r' % kind)


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    with open(argv[1], encoding='utf-8') as f:
        spec = json.load(f)
    build(spec, argv[2])
    print('생성 완료:', argv[2])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
