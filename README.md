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
배치에서는 문헌마다 보안문자가 나올 수 있습니다. 화면 없는 실행의 403은 남은 제약이며 완전 무인화는 추가 추진하지 않습니다.
[Espacenet 이슈 #1](https://github.com/khsshkk7-glitch/patent-reference-builder/issues/1)은 사용자 확인 방식으로 운영 범위를 확정했습니다.
[KIPRIS 국내 전문 수집 이슈 #2](https://github.com/khsshkk7-glitch/patent-reference-builder/issues/2)의 사이트 상세 오류는 미해결입니다.
국내 상세 연결이 시간 초과되면 KPA 영문 인쇄본을 보존하고 동일 공개번호·종별의 Espacenet 원문으로 복구하는 경로를 추가했습니다.
출처는 `KIPRIS + Espacenet`으로 기록합니다. KR20200137353A에서 보안문자 사용자 입력 후 KPA 1페이지 + 원문 19페이지의 최종 20페이지 생성·시각 검수를 완료했습니다.
접근 불가 문헌은 정상 브라우저 세션 또는 검토된 로컬 PDF manifest로 재개할 수 있습니다.

저장소 루트를 `~/.codex/skills/patent-reference-builder`에 설치하면 스킬로 사용할 수 있습니다.
Python 의존성 및 Chromium 설치 후 실행하세요. 원본 업무 파일·쿠키·브라우저 프로필·샘플 PDF는 배포하지 않습니다.
