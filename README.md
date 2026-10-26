# 안양도시공사 문서작성 스킬 (auc-docs)

메모·PDF·HWPX·회의록을 주면 Claude가 부족한 내용을 **한 번에 하나씩 질문**한 뒤,
공사 서식 그대로의 **공문서(시행문)** 또는 **내부 보고서** HWPX 파일을 만들어 줍니다.

- 사실(날짜·수신·붙임·근거·수치)은 지어내지 않고 묻습니다. 붙임은 항상 확인합니다.
- 개인정보(이름·전화·이메일)는 묻지도 옮기지도 않고 `○○○`, `031-389-○○○○`, `○○○@auc.or.kr` 로 남깁니다.
  한글에서 직접 채우세요. 결과물은 `check_privacy.py`로 자동 검사합니다.

## 설치 — claude.ai (웹·앱)

1. `dist/auc-docs.zip` 을 받습니다.
2. claude.ai → 설정 → 기능(Capabilities) → 스킬 → 스킬 업로드 → ZIP 선택.
   (코드 실행 기능이 켜져 있어야 합니다.)
3. 대화에서 "안양도시공사 공문 써줘", "회의 결과보고서 만들어줘" 처럼 요청하면 스킬이 동작합니다.

팀 공유: 조직(Team/Enterprise) 플랜이면 관리자가 조직 스킬로 올려 모두가 쓸 수 있습니다.
개인 플랜이면 각자 ZIP을 올립니다.

## ChatGPT에서 쓰기

같은 ZIP(Agent Skills 형식)을 ChatGPT의 스킬 기능에 올려 보세요(이 환경에서 직접 확인하지 못했습니다).
안 되면 **커스텀 GPT**를 만들어:
- 지침(Instructions)에 `SKILL.md` 본문과 `reference/*.md` 내용을 붙여 넣고,
- 지식(Knowledge)에 `scripts/*.py`, `templates/*.hwpx` 를 올리고,
- "코드 인터프리터"를 켭니다.

## 구성

```
auc-docs/
  SKILL.md               절차·개인정보·합리화 차단
  reference/gongmun.md   공문 규칙, 질문 목록, JSON 예시
  reference/report.md    보고서 규칙, 질문 목록, JSON 예시
  templates/*.hwpx       공사 서식(개인정보 제거)
  scripts/build_hwpx.py  JSON → HWPX
  scripts/check_privacy.py  개인정보 검사
```
Python 표준 라이브러리만 사용합니다.

## 개발

```bash
python3 -m unittest discover tests -v      # 단위 테스트
python3 skill/auc-docs/scripts/build_hwpx.py tests/fixtures/gongmun_futsal.json samples/sample.hwpx
cd skill && zip -r ../dist/auc-docs.zip auc-docs -x '*/__pycache__/*'   # 패키징
```

설계·계획·테스트 기록: `docs/`
