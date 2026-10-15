# patent-reference-builder

특허 참증 PDF를 만드는 Codex 스킬입니다.
채팅·XLSX·XLS·CSV의 특허번호를 받아 **영문 서지·초록 + 공식 공보 전문** 순서로 병합하고,
행별 처리결과 엑셀·출처/해시 기록·선택적 ZIP을 생성합니다.

- [스킬 지침](SKILL.md)
- [설치 및 실행 방법](references/usage.md)
- [CAPTCHA·브라우저 세션·검토 후 재개](references/browser-recovery.md)
- [검증 범위 및 현재 사이트 접근 제한](references/validation.md)

기본 수집원은 Espacenet이며 KR은 KIPRIS로 폴백합니다. 접근 차단·공보 종별 불일치·불완전한 PDF는 실패로 기록합니다.
현재 독립 브라우저의 Espacenet 403 및 KIPRIS 국내 전문 오류로 인해 실사이트 무인 전 과정 성공은 확인되지 않았습니다.
정상 브라우저 세션 또는 검토된 로컬 PDF manifest로 재개할 수 있습니다.

저장소 루트를 `~/.codex/skills/patent-reference-builder`에 설치하면 스킬로 사용할 수 있습니다.
Python 의존성 및 Chromium 설치 후 실행하세요. 원본 업무 파일·쿠키·브라우저 프로필·샘플 PDF는 배포하지 않습니다.
