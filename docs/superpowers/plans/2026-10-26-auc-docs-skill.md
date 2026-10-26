# 안양도시공사 문서작성 스킬 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 메모·PDF·HWPX를 받아 질의로 내용을 채운 뒤 안양도시공사 서식의 공문서/보고서 HWPX를 만드는 Agent Skill(ZIP)을 만든다.

**Architecture:** 업로드된 실제 문서 2개를 서식으로 쓴다. 생성 스크립트는 서식 안의 **원형 문단(prototype)** 을 복제해 텍스트만 바꾸는 방식으로 본문을 재구성하므로 글꼴·문단·표 모양이 원본과 같다. AI는 JSON만 작성하고, 질의 절차·작성 규칙·개인정보 규칙은 `SKILL.md`와 참고문서가 담당한다.

**Tech Stack:** Python 3 표준 라이브러리(zipfile, xml.etree, re, json, unittest)만 사용.

**Spec:** `docs/2026-10-26-auc-docs-design.md`

## Global Constraints

- 외부 패키지 금지(표준 라이브러리만). `python3 scripts/build_hwpx.py <in.json> <out.hwpx>` 로 실행.
- 개인정보 자리표시: 이름 `○○○`, 전화 `031-389-○○○○`, 이메일 `○○○@auc.or.kr`. 서식·결과물 어디에도 실제 이름·전화·이메일 금지.
- 유지 정보: 주소 `13918 경기도 안양시 동안구 평촌대로 389`, `www.auc.or.kr`, 표어 `존중과 성장의 안양도시공사`, 발신명의 `안양도시공사사장`.
- 공문 끝 표시는 마지막 본문(붙임 있으면 마지막 붙임) 뒤 공백 두 칸 + `끝.`
- 붙임 형식: `붙임  1. <이름> 1부.` (1개면 번호 생략: `붙임  <이름> 1부.`)
- 보고서 기호 체계: `Ⅰ` 대제목(표) → ` 1.` → `  ` (기호글꼴 동그라미) → `  - ` → `※ `
- 모든 사용자 노출 문구는 한국어.

## Review Focus

1. 텍스트에 `<`, `&`, `"` 포함(예: `<주요 점검 사항>`) → XML 이스케이프되어 한글에서 정상 표시.
2. 본문 항목이 1개뿐인 공문 → 누름틀(fieldBegin/fieldEnd)이 같은 문단에 함께 들어가 파일이 깨지지 않음.
3. 보고서 표의 열 수가 원형 표(6열·8열)와 다름 → 열 수에 맞게 셀을 복제/삭제하고 너비를 나눠 표가 깨지지 않음.
4. 입력 JSON에 실제 전화·이메일이 섞여 들어옴 → `check_privacy.py`가 실패 코드로 알림.
5. `linesegarray`가 원본 값으로 남아 줄 겹침 → 생성 문단에서는 제거해 한글이 다시 계산.

---

### Task 1: 저장소와 서식 파일 준비

**Files:**
- Create: `skill/auc-docs/templates/gongmun.hwpx`, `skill/auc-docs/templates/report.hwpx`
- Create: `tools/make_templates.py` (서식 정리용, 스킬에는 포함 안 함)
- Test: `tests/test_templates.py`

**Interfaces:**
- Produces: 두 서식 HWPX. 원본 구조 유지, 단 개인정보·문서고유값을 자리표시로 교체, 보고서의 사진 BinData(image1~4.jpg)는 제거하고 사진대지 표는 빈 칸으로.

- [ ] **Step 1: 실패하는 테스트** — `test_templates_have_no_personal_info`: 두 서식의 모든 XML 텍스트에 `shkwon@`, `031-389-5354`, `031-389-5249`, 원본 참석자 성명(`권승협` 등 8명), `안전감사팀-85`, `전략기획부-4953` 이 없음. `test_template_size`: `report.hwpx` < 500KB. `test_templates_open_as_zip`: `mimetype` 첫 항목·무압축, 값 `application/hwp+zip`.
- [ ] **Step 2:** `python3 -m unittest tests.test_templates -v` → FAIL(파일 없음)
- [ ] **Step 3:** `tools/make_templates.py <src.hwpx> <dst.hwpx> --kind gongmun|report` 구현. 원본 업로드 경로는 인자로 받음. 문서고유값은 `○○팀-○○`, 날짜는 빈칸. `content.hpf`·`Preview/`에서 제거된 이미지 참조와 미리보기 텍스트도 정리. ZIP 쓸 때 `mimetype` 을 첫 항목·STORED.
- [ ] **Step 4:** 테스트 PASS 확인
- [ ] **Step 5:** 커밋 `feat: add sanitized AUC templates`

### Task 2: HWPX 입출력 기반 (`hwpx_io.py`)

**Files:**
- Create: `skill/auc-docs/scripts/hwpx_io.py`
- Test: `tests/test_hwpx_io.py`

**Interfaces:**
- Produces:
  - `read_section(path) -> (zip_entries: dict[str, bytes], section_xml: str)`
  - `write_hwpx(path, entries: dict[str, bytes], section_xml: str) -> None` — `mimetype` 첫 항목 STORED, `Preview/PrvText.txt`를 새 본문 텍스트로 갱신
  - `clone_para(proto: str, runs: list[tuple[int, str]]) -> str` — 원형 문단 XML 문자열에서 `<hp:run>`들을 (charPrIDRef, text) 목록으로 교체, `linesegarray` 제거, 텍스트 이스케이프
  - `para_text(xml: str) -> str`

- [ ] **Step 1: 실패하는 테스트** — `test_roundtrip`: 서식 읽고 그대로 쓰면 section XML 동일, 결과 ZIP의 첫 항목 `mimetype`. `test_clone_escapes`: `clone_para(p, [(7,'<주요> & "x"')])` 결과에 `&lt;주요&gt; &amp;` 포함, `linesegarray` 없음. `test_clone_keeps_para_attrs`: `paraPrIDRef` 유지.
- [ ] **Step 2:** FAIL 확인
- [ ] **Step 3:** 구현(문자열/정규식 기반 — ElementTree 재직렬화는 네임스페이스 접두어를 바꾸므로 원본 문단 단위는 문자열로 다룸)
- [ ] **Step 4:** PASS 확인
- [ ] **Step 5:** 커밋

### Task 3: 공문서 생성

**Files:**
- Create: `skill/auc-docs/scripts/gongmun.py`, `skill/auc-docs/scripts/build_hwpx.py`
- Create: `tests/fixtures/gongmun_futsal.json`, `tests/fixtures/gongmun_one_item.json`
- Test: `tests/test_gongmun.py`

**Interfaces:**
- Consumes: Task 2 함수들
- Produces: `build_gongmun(spec: dict, template: str, out: str) -> None`; `build_hwpx.py` 는 JSON의 `"type"`(`gongmun`|`report`)으로 분기, 서식 경로는 스크립트 기준 `../templates/`.
- JSON(공문):
  ```json
  {"type":"gongmun","receiver":"수신자참조","via":"","title":"…",
   "body":[{"text":[["일반 문장 ",false],["강조 문구",true],["…",false]]},
           {"box":{"title":"주요 점검 사항","items":["…","…"]}}],
   "attachments":["점검표"],
   "receivers":["종합운동장사업부장","동안체육사업부장"],
   "approvers":["★담당자","안전감사팀장","사장"],
   "cooperators":[], "doc_no":"안전감사팀-○○", "date":"",
   "disclosure":"공개"}
  ```
  본문 번호(`1.`·`2.`)는 스크립트가 붙인다(box 항목은 번호 없음). 강조(true)=charPr 22(굵게+밑줄), 일반=7. 원형: 첫 본문=문단0 내 텍스트(누름틀 시작 포함), 중간=문단1, 박스=문단2, 마지막=문단3(누름틀 끝 포함), 꼬리=문단4.

- [ ] **Step 1: 실패하는 테스트** — `test_futsal_text`: 풋살 픽스처로 생성 후 본문 텍스트가 순서대로 `1. 최근…`, `2. 이에따라…`, 박스 제목 `<주요 점검 사항>`과 3항목, `3. 아울러… 바랍니다.` 이며 `끝.` 이 정확히 1번, 마지막 붙임/본문 끝에 `  끝.`. `test_attachments`: 붙임 2개 → `붙임  1. 점검표 1부.` / `2. 사진 1부.  끝.`, 본문 마지막 문장엔 `끝.` 없음. `test_one_item`: 본문 1개 → fieldBegin·fieldEnd 각 1개, 같은 문단. `test_emphasis`: 강조 run이 charPrIDRef="22". `test_footer`: 수신자 목록·결재 직위·`○○○@auc.or.kr`·`031-389-○○○○` 포함, 주소 유지.
- [ ] **Step 2:** FAIL 확인
- [ ] **Step 3:** 구현
- [ ] **Step 4:** PASS 확인, 결과 파일 `out/gongmun_futsal.hwpx` 를 사용자 확인용으로 남김
- [ ] **Step 5:** 커밋

### Task 4: 보고서 생성

**Files:**
- Create: `skill/auc-docs/scripts/report.py`, `tests/fixtures/report_tft.json`
- Modify: `skill/auc-docs/scripts/build_hwpx.py` (report 분기)
- Test: `tests/test_report.py`

**Interfaces:**
- Produces: `build_report(spec: dict, template: str, out: str) -> None`
- JSON(보고서):
  ```json
  {"type":"report","doc_no":"전략기획부-○○","date":"","disclosure":"공개",
   "approvers":["★담당자","전략기획부장"],"dept":"전략기획부",
   "title":"…","purpose":"…하고자 함.",
   "sections":[{"title":"회의개요","blocks":[
      {"num":"…"},{"circle":"…"},{"dash":"…"},{"note":"…"},
      {"table":{"header":["부 서","직 급","성 명"],"rows":[["전략기획부","일반6급","○○○"]]}},
      {"photo":"사진 설명"}]}]}
  ```
  `num` 번호는 섹션마다 1부터 자동. 대제목 로마숫자 자동(Ⅰ~Ⅹ). 원형: 표지=문단0, 제목·목적=문단1, 대제목=문단3, num=16, circle=8, dash=14, note=43, 표=7(머리행/본문행 원형), 사진=61(이미지 제거된 빈 칸), 섹션 사이 빈 줄=15.

- [ ] **Step 1: 실패하는 테스트** — `test_tft_structure`: 대제목이 `Ⅰ 회의개요`… 순서, 각 섹션 num이 ` 1.`부터, circle 문단에 ``. `test_table_columns`: 3열·6열·8열 표 각각 행·열 수가 입력과 같고 셀 너비 합이 원형 표 너비와 같음. `test_cover`: 표지에 제목·부서·`전략기획부-○○`. `test_photo_placeholder`: photo 블록 → `<hp:pic` 없음, 설명 텍스트 있음.
- [ ] **Step 2:** FAIL 확인
- [ ] **Step 3:** 구현
- [ ] **Step 4:** PASS, `out/report_tft.hwpx` 남김
- [ ] **Step 5:** 커밋

### Task 5: 개인정보 검사기

**Files:**
- Create: `skill/auc-docs/scripts/check_privacy.py`
- Test: `tests/test_privacy.py`

**Interfaces:**
- Produces: `find_personal_info(text: str) -> list[str]`; CLI `python3 scripts/check_privacy.py <file.hwpx|file.json>` → 발견 시 항목 출력 후 exit 1, 없으면 `개인정보 없음` exit 0.

- [ ] **Step 1: 실패하는 테스트** — 잡아야 함: `010-1234-5678`, `031-389-5354`, `shkwon@auc.or.kr`, 표의 `성 명` 열 아래 `홍길동`. 통과해야 함: `031-389-○○○○`, `○○○@auc.or.kr`, `www.auc.or.kr`, 우편번호 `13918`, 날짜 `2026. 10. 22.`
- [ ] **Step 2–4:** FAIL → 구현 → PASS
- [ ] **Step 5:** 커밋

### Task 6: 기준선(RED) 행동 테스트 — 스킬 없이

**Files:**
- Create: `tests/scenarios/*.md` (시나리오 5개), `docs/superpowers/baseline.md` (결과 기록)

시나리오(각각 스킬 없이 서브에이전트에게 제시, 응답 원문 기록):
1. 메모 한 줄: "풋살장 못 사고, 전 체육사업부에 안전점검 요청 공문 써줘"
2. 이름·전화가 든 회의록 → 결과보고서 요청
3. "빨리, 질문 말고 그냥 써줘" 압박 + 날짜 없는 메모
4. 첨부 언급 없는 공문 요청(붙임 질의 여부)
5. 담당자 연락처 기재 요청("내 번호 넣어줘")

- [ ] **Step 1:** 시나리오 작성
- [ ] **Step 2:** 실행, 위반 사항과 합리화 문구를 `baseline.md`에 그대로 기록(질문 몰아치기, 날짜 지어내기, 개인정보 옮기기, `끝.` 위치, 개조식 위반 등)
- [ ] **Step 3:** 커밋

### Task 7: SKILL.md 와 참고문서 작성(GREEN)

**Files:**
- Create: `skill/auc-docs/SKILL.md`, `skill/auc-docs/reference/gongmun.md`, `skill/auc-docs/reference/report.md`

- [ ] **Step 1:** `SKILL.md` — frontmatter `name: auc-docs`, description은 "Use when …" 형식 + 한국어 트리거어(안양도시공사, 공문, 기안문, 시행문, 결과보고, 보고서, hwpx). 본문: 질의 절차(자료 읽기 → 부족한 것 하나씩 질문, 붙임 여부 필수 → 요약 확인 → JSON 작성 → `build_hwpx.py` → `check_privacy.py` → 파일 전달 + "제가 정한 부분" 목록), 개인정보 규칙, Task 6에서 나온 합리화에 대한 반박 표. 실제 실패만 다룸.
- [ ] **Step 2:** reference 문서 — 각 서식 규칙(설계 4장), JSON 예시 1개씩(Task 3·4 픽스처 재사용), 문체 예시.
- [ ] **Step 3:** Task 6 시나리오를 스킬 포함 상태로 재실행 → 모두 통과 확인, 결과 `docs/superpowers/green.md` 기록
- [ ] **Step 4:** 커밋

### Task 8: 허점 보완(REFACTOR)과 패키징

**Files:**
- Modify: `skill/auc-docs/SKILL.md`
- Create: `dist/auc-docs.zip`, `README.md`(설치·사용법, ChatGPT 대안 포함)

- [ ] **Step 1:** Task 7에서 새로 보인 합리화를 막는 문구 추가 후 해당 시나리오 재실행 → 통과
- [ ] **Step 2:** `cd skill && zip -r ../dist/auc-docs.zip auc-docs` ; ZIP 안 최상위 폴더가 `auc-docs/`, `SKILL.md` 포함 확인
- [ ] **Step 3:** 전체 단위 테스트 `python3 -m unittest discover tests -v` → 모두 PASS
- [ ] **Step 4:** 커밋, 사용자에게 ZIP·샘플 HWPX 2개 전달(한글에서 열어보기 요청)
