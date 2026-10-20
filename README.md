# patent-reference-builder

특허 참증 PDF를 만드는 Codex 스킬입니다.
채팅·XLSX·XLS·CSV의 특허번호를 받아 **영문 서지·초록 + 공식 공보 전문** 순서로 병합하고,
행별 처리결과 엑셀·출처/해시 기록·선택적 ZIP을 생성합니다.

- [스킬 지침](SKILL.md)
- [설치 및 실행 방법](references/usage.md)
- [CAPTCHA·브라우저 세션·검토 후 재개](references/browser-recovery.md)
- [검증 범위 및 현재 사이트 접근 제한](references/validation.md)

기본 수집원은 Espacenet이며 KR은 KIPRIS로 폴백합니다. 접근 차단·공보 종별 불일치·불완전한 PDF는 실패로 기록합니다.
**현재 운영 방식은 Chrome 창에서 보안문자만 사용자가 입력하고 나머지를 자동 처리하는 방식입니다.**
JP 2006-198019 A로 영문 서지·초록 1페이지 + 원문 전체 9페이지 = 최종 10페이지 생성과 시각 검수를 완료했습니다.

```sh
python scripts/build_references.py --text "JP 2006-198019 A" --headed --channel chrome --interactive --human-timeout 300
```

최종 PDF는 표준 특허번호 파일명으로 사용자 **다운로드 폴더**에 저장됩니다.
다른 저장 위치는 `--out`으로 지정합니다. 동일 파일명이 있으면 기존 파일을 보존하고 `(2)`, `(3)`을 붙입니다.
결과 엑셀의 파일명 링크와 결과 JSON의 절대 경로로 최종 파일을 확인할 수 있습니다.

보안문자가 나오면 Chrome에서 숫자를 입력하고 Submit을 누릅니다. 같은 세션에서 파일 수신 후 검증·병합이 이어집니다.
사용자 입력 부담을 줄이기 위해 공식 EPO OPS 원문 연결을 추가했습니다. 계정·API 키가 필요하며
키 발급 전에는 실서비스 다운로드가 검증되지 않았습니다. [발급·로컬 연결 방법](references/ops-setup.md)을 참고하세요.
이 경로는 보안문자 자동 입력 기능이 아니며 영문 서지 웹 접근까지 완전 무인화한 것은 아닙니다.
브라우저 배치에서는 문헌마다 보안문자가 나올 수 있습니다. 화면 없는 실행의 403은 남은 제약이며,
이슈 #6에서 공식 API를 통한 원문 자동 수집을 검토·구현 중입니다. 키 발급 후 실제 검증이 남아 있습니다.
[Espacenet 이슈 #1](https://github.com/khsshkk7-glitch/patent-reference-builder/issues/1)은 사용자 확인 방식으로 운영 범위를 확정했습니다.
[KIPRIS 국내 전문 수집 이슈 #2](https://github.com/khsshkk7-glitch/patent-reference-builder/issues/2)는
일반 Chrome 연결 모드에서 **KIPRIS만 사용하는 직접 수집**을 구현하고 공개공보 3건·등록공보 B1 1건으로 검증했습니다.
독립 자동 실행 Chrome의 오류 주소 전환은 여전히 재현되므로 KIPRIS 작업에는 다음 지원 모드를 사용합니다.

```sh
python scripts/build_references.py --text "KR20200137353A" --source kipris --native-chrome --headed --no-fallback
```

`--native-chrome`은 설치된 일반 Chrome을 별도 작업용 프로필로 열고 로컬로 연결합니다.
`--no-fallback`은 KIPRIS 원문을 받지 못하면 Espacenet으로 대체하지 않고 실패로 기록합니다.
직접 수집 결과는 KPA 영문 인쇄본 + KIPRIS 공식 원문이며 출처는 `KIPRIS`입니다.
기존 방식에서 국내 상세 연결이 시간 초과되면 KPA 영문 인쇄본을 보존하고 동일 공개번호·종별의 Espacenet 원문으로 복구할 수도 있습니다.
출처는 `KIPRIS + Espacenet`으로 기록합니다. KR20200137353A에서 보안문자 사용자 입력 후 KPA 1페이지 + 원문 19페이지의 최종 20페이지 생성·시각 검수를 완료했습니다.
접근 불가 문헌은 정상 브라우저 세션 또는 검토된 로컬 PDF manifest로 재개할 수 있습니다.

저장소 루트를 `~/.codex/skills/patent-reference-builder`에 설치하면 스킬로 사용할 수 있습니다.
Python 의존성 및 Chromium 설치 후 실행하세요. 원본 업무 파일·쿠키·브라우저 프로필·샘플 PDF는 배포하지 않습니다.

서지·영문 초록 누락은 사이트 접근 오류와 구분하여 보고합니다. `--original-only`는 공식 원문을
`원문만/`에 별도 저장하며 완성 참증 성공으로 집계하지 않습니다.
영문 초록이 없으면 Codex가 동일 공보 원문 초록을 AI 번역하고, 원문 초록도 없으면 근거 명세서에서 AI 영문 요약을 작성합니다.
AI 표시가 있는 서지·초록을 앞에, 공식 원문 전체를 뒤에 병합하며 결과는 `AI 번역 보완`/`AI 요약 보완`으로 구분합니다.
[AI 보완 실행 방법](references/ai-fallback.md)을 참고하세요. 별도 API 키 없이 Codex가 번역하고 Python이 PDF를 생성합니다.
J-PlatPat 기계번역 별도 보완자료도 기존 방식으로 사용할 수 있습니다.
[자료 누락·보완자료 실행 방법](references/usage.md)을 참고하세요.
