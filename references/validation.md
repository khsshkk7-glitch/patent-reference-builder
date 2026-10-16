# 검증 기록

2026-10-15, Windows / Python 3.12에서 검증.

## 2026-10-16 — Issue #1 추가 조사

운영 결정: 사용자와 Chrome 사용자 확인 방식으로 계속 사용하기로 합의했다.
화면 없는 실행의 403을 해결하거나 완전 무인화를 추가 추진하지 않는다.
Espacenet 수집의 현재 지원 흐름은 보안문자 직접 입력 후 자동 다운로드·병합이다.
KIPRIS 이슈 #2는 별도 미해결 상태로 남는다.

- 제한된 실행 환경: `net::ERR_NETWORK_ACCESS_DENIED`. 기존에는 오류 타입만 남아 원인이 숨겨졌으므로 네트워크 오류 코드를 보존하도록 수정.
- 네트워크 허용 환경에서 화면 없는 Chromium 및 Chrome: HTTP 403 재현. 응답 Server 헤더는 cloudflare지만 이것만으로 탐지 사유는 확정할 수 없음.
- 일반 Chrome 창 모드: 페이지 로딩 완료 대기 추가 후 검색 → 동일 JP 문헌 영문 서지/초록 PDF 생성 → 원문 9페이지 화면까지 성공.
- 기존 별도 HTTP 다운로드 요청은 403. 공식 Download 버튼을 사용하면 실제 Espacenet verification 보안문자 화면이 표시됨을 스크린샷으로 확인.
- 공식 버튼 다운로드로 변경하고 `--headed --channel chrome --interactive`에서 사용자가 보안문자를 입력하는 동안 같은 세션의 파일 수신을 기다리도록 수정.
- 이후 사용자가 보안문자를 직접 입력한 실행에서 원문 9페이지 다운로드와 최종 10페이지 병합에 성공.
- 서지 항목명 폭과 숨겨진 중복 이름 인쇄를 보정하고 서지 전체·원문 표지·청구범위·도면 경계·마지막 페이지를 렌더 검수. 원문 9페이지 모두 병합 후 디코딩 콘텐츠 스트림 일치 확인.
- `--headed --channel chrome --interactive` 사용자 확인 방식은 실증 완료. 화면 없는 무인 실행의 403은 여전히 남은 제한이며 사용자 확인 방식 성공과 구분한다.


## 확인된 범위

- 요청한 KR/JP 번호 변형, US/EP/WO/CN, 공보 종류 정확 일치 및 불명확한 종류 거부.
- XLSX·CSV 원본 행 대응, 헤더 없는 CSV, 잘못된 번호/빈 번호의 실패 기록, 출원번호 헤더 구분.
- XLS 구형 입력과 복수 시트 읽기.
- PDF 순서·페이지 수·페이지 크기 보존, 기존 결과 덮어쓰기 거부.
- 검토 manifest 해시 검사, 중복 입력 재사용, 부분 실패 보고 및 ZIP.
- 네트워크를 차단한 Playwright 테스트: Espacenet UI 흐름·A4 인쇄·초록 보존·전체 PDF 페이지 수.
- 제공된 실제 샘플의 병합 회귀 검사: 원문 각 페이지의 디코딩 콘텐츠 스트림이 병합 후에도 동일함.
- 실제 KIPRIS KPA 샘플 검색과 공식 인쇄 팝업에서 A4 영문 초록 1페이지 생성. 렌더 이미지 검수 완료.
- 스킬 frontmatter 검증: skill-creator quick_validate.

## 2026-10-15 당시 실사이트 제한

독립 Playwright 세션에서 Espacenet은 HTTP 403을 반환했다. 내장 브라우저에서는 JP 샘플의
서지·영문 초록·Original document 9페이지·전체 다운로드 링크를 확인했다.
KIPRIS는 KPA 수집·인쇄에 성공했지만 국내 전문 상세 요청이 사이트 오류 주소
`fail.kipris.or.kr/error.html`로 이동하여 브라우저가 혼합 콘텐츠를 차단했다.
보안 설정을 완화하지 않았으며, 해당 세션에서 **온라인 수집부터 최종 병합까지 완주한 것으로 표시하지 않는다.**
위 내용은 최초 테스트 기록이다. 2026-10-16 Espacenet 사용자 확인 방식의 성공은 상단 추가 조사 기록을 따른다.
전문 뷰어/blob 다운로드 코드는 실제 UI 구조를 기반으로 작성했으나 정상 세션에서의 추가 실증이 필요하다.
`--profile`/`--cdp` 또는 공식 사이트에서 검토하여 받은 로컬 자료 + manifest 경로를 사용한다.

JP 샘플은 영문 서지 1 + 원문 9 = 10페이지다.
KR 제공 샘플은 영문 KPA 1 + 파일 첨부 안내지 1 + 공보 원문 19 = 21페이지다.
안내지를 빼고 요청한 두 자료만 병합하면 KR은 20페이지가 된다.
샘플 자체에는 PDF 객체 오프셋 경고가 있으며, 이는 새 수집본의 정상 여부를 판단하는 근거로 삼지 않는다.

## 재현

```sh
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m unittest discover -s tests -v
```

개인 샘플 검사(샘플 파일은 저장소에 포함하지 않음):

```powershell
$env:PATENT_SAMPLE_DIR = '샘플 PDF가 있는 폴더'
python -m unittest discover -s tests -v
```

실사이트 검증은 명시적으로 실행한다. CI에서는 외부 특허 사이트를 호출하지 않는다.

```sh
python scripts/build_references.py --text "JP 2006-198019 A" --out output/live-jp --headed --channel chrome --interactive --human-timeout 300
python scripts/build_references.py --text "KR 10-2020-0137353" --source kipris --out output/live-kr --headed
```
