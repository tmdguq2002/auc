#!/bin/bash
# HWPX를 PNG로 렌더링해 모양을 눈으로 확인한다(개발용, 스킬에는 포함 안 함).
# 준비: LibreOffice + libreoffice-java-common + H2Orestart 확장
#   apt-get install -y libreoffice-java-common
#   unopkg add --shared H2Orestart.oxt   (https://github.com/ebandal/H2Orestart)
# 주의: LibreOffice 렌더링은 근사치다. ○ 기호(기호 글꼴)가 ▯로 보이거나 표지 뒤 빈 쪽,
#       표 머리칸 글자 잘림, 요지 라벨 장식 도형(선·아이콘) 위치 어긋남은 원본에서도 똑같이 나타나는
#       렌더러 차이다. 최종 확인은 한글에서.
# 사용: bash tools/render_preview.sh <파일.hwpx> [출력폴더]
set -e
src="$1"; out="${2:-out/preview}"
mkdir -p "$out"
soffice --headless --convert-to pdf --outdir "$out" "$src" >/dev/null 2>&1
base="$(basename "${src%.hwpx}")"
pdftoppm -r 60 -png "$out/$base.pdf" "$out/$base"
ls "$out/$base"*.png
