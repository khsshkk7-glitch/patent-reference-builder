# 실행 방법

저장소 루트 자체가 설치 가능한 `patent-reference-builder` 스킬 폴더다.
Codex 스킬 폴더 아래 이 이름으로 복사하거나 복제하고 새 대화에서 사용한다.
사용자 데이터와 브라우저 프로필은 저장소 외부에 두는 것을 권장한다.

## 준비

```sh
python -m venv .venv
# Windows
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m playwright install chromium
# macOS/Linux: .venv/bin/python 사용
```

실행 명령의 `python`은 위 가상환경 실행 파일로 대체할 수 있다.

```sh
python scripts/build_references.py --text "KR1020200137353A, JP 2006-198019 A" --out output/check --dry-run
python scripts/build_references.py --text "特開2006-198019" --headed --channel chrome --interactive --human-timeout 300
python scripts/build_references.py --input "list.xlsx" --zip --headed --channel chrome --interactive --human-timeout 300
python scripts/build_references.py --input "list.xls" --column "공개번호" --country KR --out output/batch-kr --source kipris --headed --channel chrome --interactive
python scripts/build_references.py --input "list.csv" --out output/csv --profile "/absolute/path/reference-profile" --headed --channel chrome --interactive
```

온라인 Espacenet 수집은 위 Chrome 사용자 확인 명령을 우선 사용한다.
보안문자가 뜨면 사용자가 열린 Chrome에서 직접 입력하고 Submit을 누르면 된다. 다운로드 단계에서는 터미널 Enter 없이
자동으로 다음 단계로 진행한다. 단건 JP 샘플의 전체 흐름을 검증했으며, 다건은 문헌마다 사용자 입력이 필요할 수 있다.
완전 무인 실행은 운영 목표에서 제외했다. KIPRIS 국내 전문 연결이 시간 초과되면
KPA 인쇄본 + 같은 공보의 Espacenet 원문으로 자동 복구하며, Espacenet 보안문자는 사용자가 입력한다.
복합 출처는 결과에 표시한다. KIPRIS 자체 오류와 복구 경로 검증 상태는 이슈 #2 및 검증 기록을 따른다.

`.xlsx`: openpyxl, `.xls`: pandas + xlrd, CSV: UTF-8 BOM/CP949와 쉼표/탭/세미콜론을 지원한다.
첫 30행에서 헤더를 찾고, 헤더가 없으면 최초 유효 특허번호가 있는 컬럼을 찾는다.
여러 번호 컬럼이면 공개/공보 등 헤더를 출원번호보다 우선한다. `--column`으로 명시할 수 있다.
`--role`을 생략하면 출원번호 헤더는 application, 공개/공보/등록 헤더는 publication으로 판단한다.
헤더 없는 파일·일반 특허번호 헤더·채팅의 기본값은 publication이다. `--role application` 또는 `--role publication`을
명시하면 CSV/XLSX/XLS와 채팅에 모두 적용한다. 번호 헤더와 유형이 충돌하면 해당 행을 실패로 기록하고 검색하지 않는다.
명시한 유형에 맞는 번호 컬럼이 함께 있으면 그 컬럼을 우선 선택한다. `--column` 명시는 컬럼 선택에 우선하며 유형 충돌 검사는 유지한다.
`특허번호`/`Patent No.` 또는 사용자 지정의 일반 헤더는 유형을 단정하지 않으므로 명시한 `--role`을 적용할 수 있다.
dry-run/결과 JSON의 `input_role`, `input_role_source`(explicit/header/default)를 확인한다. 결과에는 정규화 입력번호와
`search_query`도 보존한다. application은 `ap=` 검색을 사용하며 검토된 출원/공보 매핑 없이 공보번호로 임의 전환하지 않는다.
한국의 권리 접두부와 11자리 U 입력의 공보/출원 구분은 [한국 번호 정규화](kr-numbering.md)를 따른다.
입력 계획의 `kr_right`(10/20/빈값)와 실제 결과의 `input_kr_right`를 확인한다. 유형 미확정 11자리 번호를 KIPRIS용 10형으로 임의 변환하지 않는다.

```sh
python scripts/build_references.py --input list.csv --role application --dry-run --out output/check
```

모든 시트를 읽으며 `--sheet`로 제한할 수 있다. 결과 파일은 원본 행·시트를 **값으로 복사**한다.
서식·매크로·차트 복제는 하지 않는다. 원본 수식은 실행되지 않는 텍스트로 보존한다.
빈 번호가 있는 데이터행과 파싱 실패행도 실패 사유를 남긴다. 완전히 빈 행은 처리하지 않는다.
헤더가 없으면 첫 유효 번호 앞의 행도 검사하며 임의로 헤더로 간주하지 않는다.
번호 컬럼을 인식하지 못하거나 지정 컬럼이 없는 시트도 각 비어 있지 않은 행을 실패로 기록한다.
확인된 번호 헤더 앞의 안내행과 `--sheet` 지정으로 대상이 아닌 시트의 데이터행은 `제외`와 사유를 기록한다.
문헌 입력 건수는 완전히 빈 행·확인된 번호 헤더를 뺀 행 수이며, 제외된 행도 이 집계에 포함한다.
헤더 없는 시트의 결과 엑셀은 결과 헤더를 위한 첫 행을 추가하므로 원본 1행은 결과 2행에 보존한다.
JSON의 `row`는 항상 원본 행 번호다. 종료 요약의 `input_rows`와 `recorded_rows` 및 상태별 건수를 대조한다.
실행 중 집계는 `work/<실행ID>/input-accounting.json`에 저장하며, 중단 시 `remaining_rows`로 미기록 행 수를 확인한다.
`--dry-run`도 전체 행의 예정·실패·제외와 사유를 남기고 같은 출력 폴더에 `input-accounting.json`을 저장한다.
한 셀에 여러 문헌이 있으면 임의로 하나만 고르지 않고 실패 처리하므로 한 행에 한 문헌으로 정리한다.

결과 폴더에는 최종 PDF, 타임스탬프가 붙은 결과 XLSX/JSON, 선택적 ZIP이 생긴다.
`--out`을 생략하면 OS에 설정된 사용자 다운로드 폴더가 기본 저장 위치다. Windows는 Known Folder API로
변경·리디렉션된 Downloads 위치를 조회한다. Linux는 XDG_DOWNLOAD_DIR 설정, macOS는 ~/Downloads를 사용한다.
Windows 위치 조회가 실패하면 오류를 알리고 `--out`으로 명시하도록 하며 임의 폴더로 저장하지 않는다.
다른 위치를 원하면 `--out "/absolute/path/folder"`로 지정한다.
`work/`에는 원본 조각·검수 양식·실패 화면이 남는다. 생성 명령의 ZIP은 `검수대기_` 접두부로 이번 생성 PDF와 보고서·검수 안내를 포함한다.
AI 보완 결과와 명시적으로 요청한 원문 단독 결과도 상태를 구분해 포함하며 실패 파일은 넣지 않는다.
중복 행은 별도 행으로 보고하지만 같은 PDF를 재사용한다. 이전 실행의 동일 파일명이 있으면
`특허번호 (2).pdf`, `(3).pdf` 순서로 새 파일을 만든다. 기존 파일은 보존한다.
병합본과 원문 단독 파일 모두 출력 폴더의 `.reference-*.pdf.part`에 쓰기·flush/fsync·PDF 페이지 검증·해시 계산을 끝낸 뒤
동일 파일시스템의 하드 링크로 최종 이름을 한 번에 공개한다. 이미 존재하는 이름은 덮어쓰지 않는다.
원문 단독은 저장된 바이트의 SHA-256도 원본 바이트와 대조한다. 쓰기·검증·최종 이름 생성이 실패하면 해당 임시 파일을 정리하고 건별 실패로 보고한다.
하드 링크를 지원하지 않는 파일시스템·공유폴더에서는 오류를 보고하며 불완전한 최종 복사로 전환하지 않는다.
이때 `--out`으로 하드 링크가 가능한 폴더(예: 로컬 NTFS)를 지정한다.
강제 프로세스 종료·전원 차단은 정리 코드를 실행하지 못해 `.pdf.part`가 남을 수 있다. 이 임시 파일을 완성 PDF로 취급하지 않는다.
결과 JSON의 `output_path`와 종료 요약의 `files`는 실제 최종 파일의 절대 경로다.
결과 엑셀은 실제 파일명을 기록하고 해당 PDF를 여는 하이퍼링크를 제공한다.

생성 명령 종료코드: `0` 전건 생성 완료(최종 검수 완료를 의미하지 않음), `1` 일부/전체 건별 실패 또는 수집·번역 검토 대기, `2` 잘못된 실행 옵션·입출력 오류.
생성 직후 공식 자료도 `complete_reference=false`다. `official_materials_complete`는 공식 구성자료 확보 여부이며
`final_review_complete` 및 `review_status`와 구분한다. 최종 검수 절차·결과 갱신·완료 ZIP은 [최종 검수 기록](final-review.md)을 따른다.
`--dry-run`은 문헌 검색·PDF 생성을 하지 않고 입력 계획을 `input-plan.json`에 저장한다.

## 브라우저 옵션

Espacenet 원문은 `--original-method auto|browser|ops`로 선택한다. 기본 `auto`는 OPS 환경 키가 있으면
공식 API를 우선 사용하고 없으면 기존 브라우저다. [OPS 계정·키 발급과 로컬 숨김 입력](ops-setup.md)을 따른다.
API 원문은 사이트 뷰어 페이지 수와 대조하고 공식 페이지 PDF 순서 조립으로 기록한다.
키 없는 실제 API 수집 검증은 남아 있으며, API 실패를 브라우저 사용자 인증으로 조용히 전환하지 않는다.

KIPRIS를 이용할 때는 일반 Chrome 연결 모드를 우선 사용한다.

```sh
python scripts/build_references.py --input "list.xlsx" --source kipris --native-chrome --headed --no-fallback --zip
```

`--native-chrome`은 설치된 Google Chrome을 별도 임시 프로필로 실행하고 127.0.0.1의 임시 포트로 연결한다.
작업이 끝나면 자신이 연 브라우저만 종료하며 사용자의 평소 Chrome 프로필은 사용하지 않는다.
`--headed`가 필요하고 `--profile`, `--cdp`, `--channel msedge`와 함께 쓸 수 없다.
준비된 사용자 작업용 Chrome이 있으면 기존 `--cdp` 옵션도 사용할 수 있다.
`--no-fallback`은 `--source kipris`와 함께 사용하며 KIPRIS 원문 실패 시 Espacenet으로 대체하지 않는다.
기본 `auto` 방식은 기존과 같이 Espacenet 우선이며, KR의 KIPRIS 폴백을 예상하는 혼합 배치도 처음부터
`--native-chrome --headed`로 열 수 있다. 보안문자 입력이 필요한 배치에는 `--interactive`를 추가한다.

- `--headed`: 화면이 보이는 Chromium. 기본은 headless.
- `--channel chrome` 또는 `--channel msedge`: 설치된 브라우저 채널.
- `--profile PATH`: 참증 작업 전용 프로필. 평소 사용 중인 기본 프로필을 지정하지 않는다.
- `--cdp http://127.0.0.1:9222`: 사용자가 디버깅 모드로 준비한 브라우저에 연결한다.
  기존 탭을 닫거나 브라우저 프로세스를 종료하지 않는다. 로컬 주소만 허용한다.
- `--interactive --human-timeout 300`: Espacenet 공식 다운로드에서는 사용자 입력 후 파일 수신을 최대 300초 기다리고 자동 진행한다.
  다른 접근 제한의 복구 안내에서 Enter를 요청하는 경우에만 터미널 Enter로 재시도한다.
- `--timeout 40 --retries 3 --delay 2`: 개별 대기 초, 탐색 최대 시도 횟수, 문헌 간 간격.

수집기는 확인한 UI에 대해 동작한다. 사이트 변경이나 접근 제한 때 복구 문서를 따라 검토된 자료로 재개한다.

## 영문 서지·초록 누락 시 별도 자료

`OFFICIAL_DATA_MISSING`과 `missing_fields`는 접근 차단과 다른 공식 화면의 자료 누락이다.
해당 문헌을 완성 참증 성공으로 처리하지 않는다. 원문만 요청한 경우:

```sh
python scripts/build_references.py --text JP3102826U --native-chrome --headed --original-only --interactive --zip
```

다운로드 폴더의 `원문만/JP 3102826 U.pdf`에 공식 원본 바이트를 보존한다.
보고서는 `status=원문만`, `result_type=original_only`, `complete_reference=false`, 영문 누락 항목을 기록한다.
집계는 `success`(완성 참증), `original_only`, `failed`를 구분한다. 요청한 원문 단독 수집이 끝나면 종료코드는 0이다.
생성 ZIP도 `검수대기_원문만_…zip`이며 내부의 별도 폴더를 보존한다.

J-PlatPat의 JP U 영문 기계번역을 사용자가 **별도 보완자료로 명시적으로 허용했을 때만**:

```sh
python scripts/jplatpat_supplement.py --text JP3102826U --source-url https://www.j-platpat.inpit.go.jp/c1801/PU/JP-3102826/25/en --acknowledge-machine-translation --native-chrome --headed
```

공식 UI에서 얻은 동일 공보 영문 영구 URL을 전달한다. 다른 공보·종별·출처는 거절한다.
출처 번역문을 다시 번역하거나 보충하지 않고 인쇄용으로 배치한다. 공식 기계번역 고지와 대표도면을 보존하며
`기계번역 보완자료/JP 3102826 U.pdf`에 `MACHINE-TRANSLATED SUPPLEMENT — NOT A COMPLETE REFERENCE`를 표시한다.
별도 JSON은 `status=보완자료`, `complete_reference=false`이며 일반 참증 병합에 사용하지 않는다.
미번역·대표도면 로드 실패는 중단하고 근거 화면을 보존한다. JP3102826U 외 문헌은 개별 검증이 필요하다.

## AI 번역·요약을 원문과 병합

현재 스킬은 영문 초록을 못 찾으면 Codex가 같은 공보 원문 초록을 번역해 보완한다.
원문 초록도 없으면 AI 작성 요약으로 구분한다. [AI 보완 작성·검토 JSON 및 배치 명령](ai-fallback.md)을 따른다.
결과는 `AI 번역 보완`/`AI 요약 보완`, `ai_assisted_reference`이며 공식 자료 성공 건수와 별도로 집계한다.
AI 보완 보고서의 `complete_reference=false`는 공식 영문 자료가 모두 갖춰진 참증이 아니라는 뜻이며 최종 검수 후에도 유지한다.
AI 표시 표지와 공식 원문 전문이 병합된 최종 PDF는 정상적으로 생성해 전달한다.
