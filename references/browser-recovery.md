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
이 모드는 무인 실행이 아니며 보안문자 처리 후 최종 병합은 추가 실사이트 검증이 필요하다.
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

- [Espacenet 서지사항 인쇄](https://worldwide.espacenet.com/patent/help/print-bibliographic-data-and-other-views)
- [Espacenet 전문 다운로드](https://worldwide.espacenet.com/patent/help/originaldocumentdownloadfeature)
- [EPO 릴리스 안내: 인용 시 원문 확인](https://www.epo.org/en/searching-for-patents/technical/espacenet/release-notes)
- [Playwright 다운로드](https://playwright.dev/python/docs/downloads)
- [Playwright 기존 브라우저 연결](https://playwright.dev/python/docs/api/class-browsertype)
