# patent-reference-builder

특허 참증 PDF를 만드는 Codex 스킬입니다.
채팅·XLSX·XLS·CSV의 특허번호를 받아 **영문 서지·초록 + 공식 공보 전문** 순서로 병합하고,
행별 처리결과 엑셀·출처/해시 기록·선택적 ZIP을 생성합니다.

- [스킬 지침](SKILL.md)
- [설치 및 실행 방법](references/usage.md)
- [CAPTCHA·브라우저 세션·검토 후 재개](references/browser-recovery.md)
- [검증 범위 및 현재 사이트 접근 제한](references/validation.md)

기본 수집원은 Espacenet이며 KR은 KIPRIS로 폴백합니다. 접근 차단·공보 종별 불일치·불완전한 PDF는 실패로 기록합니다.
**기본 운영은 저장된 사용자 환경변수로 OPS 원문을 받는 방식입니다.** 서지·전문 뷰어 확인에는 Chrome을 사용합니다.
키 설정이 없으면 로컬 설정을 안내하며, 사용자가 브라우저 다운로드를 선택할 때만 보안문자 입력을 요청합니다.
JP 2006-198019 A로 영문 서지·초록 1페이지 + 원문 전체 9페이지 = 최종 10페이지 생성과 시각 검수를 완료했습니다.

```sh
python scripts/build_references.py --text "JP 2006-198019 A" --original-method ops --native-chrome --headed
```

최종 PDF는 표준 특허번호 파일명으로 사용자 **다운로드 폴더**에 저장됩니다.
다른 저장 위치는 `--out`으로 지정합니다. 동일 파일명이 있으면 기존 파일을 보존하고 `(2)`, `(3)`을 붙입니다.
결과 엑셀의 파일명 링크와 결과 JSON의 절대 경로로 최종 파일을 확인할 수 있습니다.
PDF 생성 직후는 **최종 검수 대기**입니다. 공식/AI/기계번역 자료 유형과 최종 검수 상태를 별도로 기록합니다.
앞장·원문 첫장/끝장·청구범위/도면 경계와 인명·번호를 확인하고 [최종 검수 기록](references/final-review.md)을 적용하면
검수결과 엑셀/JSON과 검수 완료 PDF만 담은 ZIP을 별도로 생성합니다. 생성 ZIP은 `검수대기_`로 표시합니다.

보안문자가 나오면 Chrome에서 숫자를 입력하고 Submit을 누릅니다. 같은 세션에서 파일 수신 후 검증·병합이 이어집니다.
기본 Espacenet 원문 수집은 사용자 환경변수 `EPO_OPS_KEY` / `EPO_OPS_SECRET`을 쓰는 공식 EPO OPS 방식입니다.
정상 설정되면 매번 키를 입력하지 않습니다. `python scripts/ops_environment.py --status`로 존재 여부만 확인하고,
Windows의 `--setup`으로 로컬 숨김 입력 창에서 등록·교체한 뒤 Codex를 재시작합니다.
값이 없거나 인증 오류가 나면 [환경변수 설정·복구 안내](references/ops-setup.md#환경변수를-기본으로-사용)를 따릅니다.
이 경로는 보안문자 자동 입력 기능이 아니며 영문 서지 웹 접근까지 완전 무인화한 것은 아닙니다.
브라우저 배치에서는 문헌마다 보안문자가 나올 수 있습니다. 화면 없는 실행의 403은 남은 제약이며,
이슈 #6에서 공식 API 단건·다건 원문 수신을 검증했으며 JP 두 건의 최종 10/13페이지 PDF를 검수했습니다.
스캔 표지·최종 시각 검수와 서지 웹 접근은 남습니다.
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
Espacenet에 비영문 초록과 빨간 Patent Translate 버튼이 있으면 [사이트 기계번역](references/patent-translate.md)을 먼저 확인합니다.
실제 영어 번역이 나오면 출처·고지를 보존하고 영문 서지는 원문에서 보완해 `사이트 기계번역 보완`으로 병합합니다.
AI 표시가 있는 서지·초록을 앞에, 공식 원문 전체를 뒤에 병합하며 결과는 `AI 번역 보완`/`AI 요약 보완`으로 구분합니다.
[AI 보완 실행 방법](references/ai-fallback.md)을 참고하세요. 별도 API 키 없이 Codex가 번역하고 Python이 PDF를 생성합니다.
J-PlatPat 기계번역 별도 보완자료도 기존 방식으로 사용할 수 있습니다.
[자료 누락·보완자료 실행 방법](references/usage.md)을 참고하세요.
