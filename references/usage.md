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
모든 시트를 읽으며 `--sheet`로 제한할 수 있다. 결과 파일은 원본 행·시트를 **값으로 복사**한다.
서식·매크로·차트 복제는 하지 않는다. 원본 수식은 실행되지 않는 텍스트로 보존한다.
빈 번호가 있는 데이터행과 파싱 실패행도 실패 사유를 남긴다. 완전히 빈 행은 처리하지 않는다.
한 셀에 여러 문헌이 있으면 임의로 하나만 고르지 않고 실패 처리하므로 한 행에 한 문헌으로 정리한다.

결과 폴더에는 최종 PDF, 타임스탬프가 붙은 결과 XLSX/JSON, 선택적 ZIP이 생긴다.
`--out`을 생략하면 OS에 설정된 사용자 다운로드 폴더가 기본 저장 위치다. Windows는 Known Folder API로
변경·리디렉션된 Downloads 위치를 조회한다. Linux는 XDG_DOWNLOAD_DIR 설정, macOS는 ~/Downloads를 사용한다.
Windows 위치 조회가 실패하면 오류를 알리고 `--out`으로 명시하도록 하며 임의 폴더로 저장하지 않는다.
다른 위치를 원하면 `--out "/absolute/path/folder"`로 지정한다.
`work/`에는 원본 조각과 실패 화면이 남는다. ZIP은 이번 실행에서 성공한 PDF와 보고서만 포함한다.
중복 행은 별도 행으로 보고하지만 같은 PDF를 재사용한다. 이전 실행의 동일 파일명이 있으면
`특허번호 (2).pdf`, `(3).pdf` 순서로 새 파일을 만든다. 기존 파일은 보존한다.
결과 JSON의 `output_path`와 종료 요약의 `files`는 실제 최종 파일의 절대 경로다.
결과 엑셀은 실제 파일명을 기록하고 해당 PDF를 여는 하이퍼링크를 제공한다.

종료코드: `0` 전건 성공, `1` 일부/전체 건별 실패, `2` 잘못된 실행 옵션·입출력 오류.
`--dry-run`은 문헌 검색·PDF 생성을 하지 않고 입력 계획을 `input-plan.json`에 저장한다.

## 브라우저 옵션

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
