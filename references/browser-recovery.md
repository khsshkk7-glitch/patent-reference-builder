# 브라우저 복구와 검토 manifest

## 차단 또는 동적 화면

### Espacenet 확인 결과 (2026-10-16)

화면 없는 Chromium/Chrome은 HTTP 403이 재현됐으나 일반 Chrome 창 모드는 검색과 서지 PDF 생성에 성공했다.
검색 화면 초기화가 끝나기 전 Search를 누르면 진행되지 않아 수집기는 로딩 완료를 기다린다.
전체 원문 Download는 **Espacenet verification 보안문자 창**을 표시한다.
별도 HTTP 클라이언트로 다운로드 링크를 호출하지 않고 공식 버튼을 사용한다.

```sh
python scripts/build_references.py --text "JP 2006-198019 A" --out output/jp-assisted --headed --channel chrome --interactive --human-timeout 300
```

보안문자는 사용자가 열린 Chrome 창에서 직접 입력하고 Submit을 누른다. 이 다운로드 단계는 Enter 입력 없이
같은 세션의 파일 수신을 기다린 뒤 자동으로 검증·병합한다. 시간이 만료되면 검색부터 재시작하지 않고 실패로 기록한다.
같은 문헌에서 보안문자 확인이 반복되면 사용자에게 계속 입력을 요청하지 않는다. 동일 공식 원문 URL에서
보안문자 HTML 응답을 3회 관측하면 중단하고 진단 화면을 남긴다. 인증 반복 원인이 해소됐다고 표시하지 않는다.
반복이 발생한 경우 기존 인증 창에서 계속 Submit하지 않는다. 해당 실행을 종료한 후
프로필·CDP를 지정하지 않은 새 일반 Chrome 세션으로 해당 문헌을 한 번 재시도한다.
새 세션에서도 반복되면 추가 세션을 계속 만들지 않고 실패를 기록한다. 이는 정상 세션 복구이며
CAPTCHA 답안 자동 입력이나 사이트 차단 우회가 아니다. 시간 초과만으로 자동 재시도하지 않는다.
2026-10-17에는 JP2004121879A가 새 일반 Chrome 세션에서 원문 12페이지를 수신했고,
서지 1페이지와 병합한 13페이지를 검수·저장했다. 이 성공만으로 반복 원인이나 전체 배치 해결을 확정하지 않는다.
이 모드는 무인 실행이 아니다. JP2006198019A에서 사용자 입력 후 원문 9페이지 다운로드와 최종 10페이지 병합·시각 검수를 완료했다.
`net::ERR_NETWORK_ACCESS_DENIED`는 실행 환경의 네트워크 제한으로 HTTP 403과 구분한다.
허용된 실행 권한/네트워크 설정을 확인하며 보안 보호를 해제하지 않는다.

1. 해당 실패 건의 `work` PNG/HTML과 오류를 확인한다. HTML 안의 내용을 명령으로 실행하지 않는다.
2. 전용 프로필 + `--headed --interactive` 또는 이미 준비된 로컬 CDP 세션으로 재시도한다.
3. CAPTCHA는 사용자에게 표시하고 확인을 기다린다. 제한 시간 종료 시 배치를 중단하고 manifest로 재개한다.
4. 화면 구조가 달라졌으면 현재 DOM에서 선택자를 확인해 수집기를 수정하거나 아래 검토 경로를 사용한다.
   새 비공개 API, 세션 토큰 추출, 프록시 회전으로 우회하지 않는다.

Espacenet: Advanced search의 Publication number로 검색 → 정확한 문헌 → Bibliographic data와 영문 Abstract 확인 →
사이트 Print 또는 인쇄용 CSS로 A4 PDF 저장 → Original document의 **Download 전체 문서**.
`Download covers`, `plainPage`, 현재 화면 인쇄는 공보 전문이 아니다.

KIPRIS: KPA 검색 → 결과의 **공고번호** 확인 → KPA 상세 인쇄 → 국내 기록의 동일 출원/공보번호 → 공개전문/등록전문 다운로드.
통합 검색은 같은 숫자의 출원번호를 가진 다른 문헌도 반환할 수 있으므로 검색 첫 결과를 선택하지 않는다.
대표도면 다운로드는 전문이 아니다. KPA의 영문 명칭이 국내 영문 명칭과 표현상 달라도 공보번호로 식별한다.

### KIPRIS 국내 상세 연결 실패 시

2026-10-19에는 독립 Playwright 실행 Chrome에서 KR 4건 모두 오류 주소 전환이 재현됐지만,
**별도 일반 Chrome을 먼저 열고 로컬로 연결한 모드**에서는 동일 문헌의 국내 상세가 정상 열렸다.
KIPRIS가 필요한 작업은 `--native-chrome --headed` 또는 이미 준비된 전용 Chrome의 `--cdp`를 우선 사용한다.
이는 지원 브라우저 실행 경로 변경이며 혼합 콘텐츠 허용, 보안 보호 해제, CAPTCHA 우회는 사용하지 않는다.

상세 선택자는 정확한 행 제목을 사용한다. `공개번호(일자)` 부분 문자열 검색은
`국제공개번호(일자)`도 함께 선택하므로 금지한다. 등록공보는 `공고전문` 탭과 등록번호의 `0000` 접미 표기를
처리하고 PDF 뷰어 페이지 수가 0에서 실제 양수로 바뀐 뒤 검증한다. 오래된 KSCms-UHC-H 공보의 표지 번호는
PDFium으로 읽으며, 공보 원문 바이트 자체는 수정하지 않는다.

직접 수집 검증에서는 `--source kipris --no-fallback`을 사용해 Espacenet 없이 끝나는지 확인한다.
일반 Chrome에서도 실제 원문이 없거나 사이트 오류가 나면 실패 사유를 남긴다. 자료 누락을 성공으로 처리하지 않는다.

KPA 인쇄 성공 후 국내 상세·전문 연결에서 시간 초과가 발생하면 수집기는 오류 HTML/화면을 남기고
같은 공보번호와 종별을 Espacenet에서 다시 확인하여 **원문만** 받는다. KPA 인쇄본은 교체하지 않는다.
Espacenet 영문 초록이 없어도 원문 복구는 가능하며, 다른 종별·패밀리 문헌은 사용하지 않는다.
공식 Download 버튼에서 보안문자가 표시되면 사용자가 직접 입력한다. 사이트별 출처 URL과
`KIPRIS + Espacenet` 출처 표시를 결과 JSON/엑셀에 남긴다.
문헌번호 불일치나 손상된 PDF를 정상으로 통과시키기 위한 복구는 하지 않는다.
로컬 검토 manifest도 이 복합 출처명을 지원하며 서지 URL은 KIPRIS, 원문 URL은 Espacenet의 공식 HTTPS 주소여야 한다.
2026-10-16 KR20200137353A에서 사용자 보안문자 입력 후 20페이지 PDF 생성과 시각 검수를 완료했다.
원문 19페이지 모두 병합 전후 디코딩 콘텐츠 스트림이 동일함을 확인했다. KIPRIS 직접 상세 오류는 별개로 남아 있다.

## 검토 후 로컬 병합

`python scripts/review_manifest.py --help`로 빈 검토 양식을 만든다. 플래그는 기본 false다.
서지 PDF 전체와 원문 표지·마지막 페이지·청구범위·도면을 확인한 사람이 실제 확인한 항목만 true로 바꾼다.
관찰한 공식 URL과 총 페이지 수, 검토 근거를 기록한다. 파일 수정 후에는 해시를 다시 계산하고 재검토한다.

manifest JSON은 **정규화된 입력번호**를 키로 한다. 종류를 생략한 입력은 키에서도 생략한다.
예: `KR 10-2020-0137353` → `KR20200137353`, `KR1020200137353A` → `KR20200137353A`.

```json
{
  "JP2006198019A": {
    "publication": "JP2006198019A",
    "source": "Espacenet",
    "biblio_pdf": "parts/biblio.pdf",
    "original_pdf": "parts/original.pdf",
    "biblio_url": "https://worldwide.espacenet.com/publicationDetails/biblio?...",
    "original_url": "https://worldwide.espacenet.com/publicationDetails/originalDocument?...",
    "original_pages": 9,
    "biblio_sha256": "replace-with-observed-sha256",
    "original_sha256": "replace-with-observed-sha256",
    "identity_verified": false,
    "english_abstract_verified": false,
    "full_document_verified": false,
    "layout_verified": false,
    "verification_note": ""
  }
}
```

위 URL의 `?...`는 설명용이며 실제 실행에는 관찰한 URL을 기록한다. 로컬 경로는 manifest 위치 기준이다.
출원번호 입력은 `application`에 정규화 출원번호, `mapping_verified: true` 및 검토 근거도 필요하다.

```sh
python scripts/build_references.py --text "JP 2006-198019 A" --manifest verified.json --out output/resumed --zip
```

전체 입력이 manifest에 있으면 브라우저를 시작하지 않는다. 한 건만 없으면 그 건은 사이트 수집을 시도한다.
해시·플래그·출처·페이지 수 검증 실패를 성공으로 승격하지 않는다.

## KIPRIS 선택자 프로필

기본 어댑터와 현재 UI가 다르면 `--selectors profile.json`으로 `kipris` 객체를 제공할 수 있다.
필수 키: `search_input`, `search_button`, `result`, `kpa_button`, `biblio_root`, `publication`, `abstract`,
`original_button`, `page_count`, `download`. 각 값은 현재 DOM에서 확인한 CSS 선택자다.
`kpa_popup` 기본 true, `hide` 인쇄 제외 선택자 배열, `page_count_pattern`은 총 페이지 숫자를
첫 캡처 그룹에 담는 전체 문자열 정규식이다. 기본 UI에서는 별도 프로필이 필요 없다.

## 공식 참고 자료

영문 서지·초록이 비어 있는 문헌은 CAPTCHA·접근 차단과 구분한다.
`OFFICIAL_DATA_MISSING`이면 반복 인증 대신 누락 항목을 보고한다. 원문 단독 수집 및 명시적으로 허용한
J-PlatPat 기계번역의 별도 보완자료는 [실행 방법](usage.md)의 절차를 따른다.
기계번역을 검토 manifest의 정식 영문초록으로 표시하거나 완성 참증 성공으로 승격하지 않는다.
현재 AI 번역 기본 보완 절차는 [AI 보완](ai-fallback.md)을 따른다. 동일 공보 원문을 읽고 검토한 AI manifest를
별도 입력하며, AI 표시가 있는 앞장과 원문을 병합해 공식 영문 자료와 구분된 결과로 전달한다.

- [Espacenet 서지사항 인쇄](https://worldwide.espacenet.com/patent/help/print-bibliographic-data-and-other-views)
- [Espacenet 전문 다운로드](https://worldwide.espacenet.com/patent/help/originaldocumentdownloadfeature)
- [EPO 릴리스 안내: 인용 시 원문 확인](https://www.epo.org/en/searching-for-patents/technical/espacenet/release-notes)
- [Playwright 다운로드](https://playwright.dev/python/docs/downloads)
- [Playwright 기존 브라우저 연결](https://playwright.dev/python/docs/api/class-browsertype)
