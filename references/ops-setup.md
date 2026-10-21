# EPO OPS 원문 연결 — Issue #6

## 현재 지원 범위

EPO는 자동 수집에 공식 OPS 및 European Publication Server REST 사용을 안내한다.
OPS는 Espacenet과 같은 원천 데이터베이스를 사용하며, 인증된 API로 공보 이미지 정보를 받은 뒤
각 페이지 PDF를 순서대로 받아 전체 전문을 조립할 수 있다. 보안문자 숫자를 인식해 입력하는 기능이 아니다.

현재 구현은 **Espacenet 영문 서지 인쇄 및 전문 뷰어 확인 → OPS 원문 페이지 수집**이다.
서지 웹 접근까지 모두 API로 바꾼 것은 아니며, 웹 서지 단계의 접근 제한이나 자료 누락은 남는다.
KIPRIS 직접 수집은 기존 방식이다. 따라서 계정 발급만으로 모든 문헌의 완전 무인화를 보장하지 않는다.
2026-10-20 API 키가 없어 인증된 실다운로드는 미검증이며 Issue #6은 열어둔다.

## 사용자의 최초 발급 절차

1. [EPO 개발자 계정 등록](https://developers.epo.org/user/register)에서 본인·회사 정보를 입력한다.
   일반 EPO 계정과 OPS 개발자 계정은 구분된다. 비밀번호·회사 정보·약관 동의와 가입 보안문자는 사용자가 직접 처리한다.
2. 계정 유형은 무료 사용을 원하면 **Non-paying**을 선택한다. 유료 이용을 자동 신청하지 않는다.
   [EPO 안내](https://www.epo.org/en/searching-for-patents/data/web-services/ops)에 따르면 비유료 한도는 주 4GB다.
   현재 포털 조건을 확인하며 계정 승인·활성화 안내를 기다린다. 승인 시간을 임의로 약속하지 않는다.
3. 승인 메일 수신 후 [개발자 포털 로그인](https://developers.epo.org/user/login) → **My Apps**에서 앱을 정의하고
   **Consumer Key / Consumer Secret**을 발급받는다. 공식 OPS 3.2 매뉴얼의 Client credentials 절차에 따른다.
   앱 이름은 예를 들어 `patent-reference-builder`로 지정할 수 있다. 키·Secret을 채팅·GitHub 이슈에 붙여 넣지 않는다.
4. 발급 후 아래 실행 도우미를 로컬 터미널에서 실행한다. 두 값을 숨김 입력받아 이번 프로세스에서만 사용하며 파일로 저장하지 않는다.

```sh
python scripts/run_with_ops.py --text "JP 2006-198019 A" --native-chrome --headed --zip
python scripts/run_with_ops.py --input list.xlsx --native-chrome --headed --zip
```

이미 로컬 환경에 `EPO_OPS_KEY`, `EPO_OPS_SECRET`을 설정했다면 기존 명령에 다음 옵션을 쓸 수 있다.

```sh
python scripts/build_references.py --text "JP 2006-198019 A" --original-method ops --native-chrome --headed --zip
```

`auto`(기본)는 키가 있으면 OPS, 없으면 기존 브라우저다. `browser`는 기존 방식을 명시적으로 선택한다.
`ops`는 API 사용을 강제하고 키가 없으면 명확히 중단한다. API 인증·한도·문헌 누락 실패는 CAPTCHA로 자동 전환하지 않는다.
키를 발급받은 사용자가 실제 연결 검증을 요청하면, 먼저 JP 단건·기존 검수용 다건에서 수신·전문 검증을 진행한다.

## 검증 및 기록

- API의 동일 국가·공보번호·종별 `FullDocument/fullimage`만 사용한다. 다른 패밀리·종별·firstpage/thumbnail은 거절한다.
- API 전체 페이지 수와 Espacenet 전문 뷰어 전체 페이지 수가 일치해야 한다.
- 각 페이지가 정상 단일 페이지 PDF인지 확인하고 1~끝까지 순서대로 조립한다. 명세서·청구범위·도면을 모두 유지한다.
- 이것은 공식 개별 페이지 PDF의 조립본이다. 웹에서 받은 단일 원본 PDF와 바이트가 같다고 주장하지 않는다.
- `ops-download.json`에 문헌·출처·페이지별 해시·조립본 해시를 남기며 토큰·키·Secret은 기록하지 않는다.
- 요청은 순차 처리하고 간격을 둔다. HTTP 인증·한도 오류를 자동 반복하지 않는다. 토큰은 프로세스 메모리에만 둔다.
- 일반 브라우저의 `download_metrics`에는 매칭한 다운로드 HTML에서 검출한 보안문자 횟수, 수신/반복/시간 초과 상태 및 대기 시간을 기록한다.
  검출 0은 모든 화면에서 보안문자가 전혀 없었다는 보장이 아니다. 실제 사용자 개입 횟수와 전체 실행 검증을 구분한다.

## 공식 근거

- [OPS 서비스·등록·인증·이용량](https://www.epo.org/en/searching-for-patents/data/web-services/ops)
- [자동 수집용 REST 경로 안내](https://www.epo.org/en/service-support/ordering/fair-use)
- [전체 전문 페이지 PDF 수집 방식](https://www.epo.org/en/service-support/faq/searching-patents/open-patent-services/search-queries-tips-and-tricks/what-do-0)
- [OPS 3.2 공식 OpenAPI 명세](https://ops.epo.org/wsdl/ops.yaml)
