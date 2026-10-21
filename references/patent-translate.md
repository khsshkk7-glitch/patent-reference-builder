# Espacenet Patent Translate 보완

비영문 초록이 화면에 있고 빨간 **Patent Translate** 버튼이 있을 때 사용한다.
EPO/Google의 사이트 기계번역이며 OPS 사용자 계정의 API 키 발급과는 다른 기능이다.

## 실제 화면에서 확인

1. 서지 화면 공보번호·종별과 비영문 초록을 확인하고, 화면의 번역 버튼을 누른다.
2. 새 번역 포털에서 English를 선택한다. 결과가 다른 새 탭으로 열릴 수도 있으므로 탭을 확인한다.
3. `ABSTRACT <정확한 공보번호·종별>` 제목, 영어 본문, 기계번역 고지가 실제 표시돼야 성공이다.
   원래 포털의 `Loading Translation... 100%`만으로 완료를 판정하지 않는다.
4. `SpikeArrest` 또는 요청 과부하가 표시되면 이를 문헌 부재로 판정하지 않는다.
   다른 독립 작업을 진행하며 기다린 뒤 한 번만 재시도한다. 계속 실패하면 원문 AI 번역 경로를 사용한다.
   포털 URL의 앱 키·PDF 임시 토큰을 추출해 직접 재호출하거나 저장소에 공개하지 않는다.
5. 사이트 번역문을 다시 쓰거나 교정해 원문과 섞지 않는다. 사이트 본문·고지와 원문 표지를 별도로 대조한다.
   비어 있는 서지는 동일 원문에서 번역·로마자 표기해 보완하고, 공식 영문 철자를 확인하지 못한 이름은 그 사실을 표시한다.

## 병합 manifest

[AI 보완 manifest](ai-fallback.md)의 기본 원문·페이지·해시·근거·검토 항목을 그대로 유지한다.
단, 사이트 번역문을 사용하는 경우 다음 필드를 사용한다.

- `translation_type`: `site_machine_translation`
- `source_abstract_available`: `true`, `source_kind`: `abstract`
- `source_text`: 같은 공보의 비영문 원문 초록
- `english_abstract`: 사이트가 실제 표시한 영어 번역문 전체 (AI 작성문을 넣지 않음)
- `site_translation_url`: 실제 확인한 EPO 번역 포털 URL. COUNTRY/NUMBER/KIND/TRGLANG=en을 유지하고 앱 키·임시 토큰은 제외
- `site_translation_notice`: 화면의 기계번역 고지 전체
- `site_translation_verified`: 동일 문헌의 실제 결과를 대조한 경우에만 `true`
- `bibliography_note`: 영문 서지 출처와 AI 번역/로마자 표기 여부

```sh
python scripts/build_references.py --text "KR 20-0355113 Y1" --ai-manifest site-manifest.json --zip
```

현재 스크립트는 검토된 사이트 번역 JSON을 받아 앞장과 원문 전체를 병합한다.
웹 번역 버튼 클릭·언어 선택은 실행 중인 Codex가 브라우저 UI로 수행하며 Python이 사이트 비공개 번역 API를 호출하지 않는다.
결과 `translation_type=site_machine_translation`, `result_type=site_machine_translated_reference`,
`status=사이트 기계번역 보완`, `complete_reference=false`로 기록하고 `site_translated`로 별도 집계한다.
영문 서지만 AI 보완했다면 `ai_provenance`에는 그 서지만 기록하고, 초록·고지는 `site_translation_provenance`에 보존한다.
앞장은 `SITE MACHINE TRANSLATION - EPO PATENT TRANSLATE`를 표시하며 사이트 고지를 보존한다.
이것은 요청한 병합 PDF의 완료 결과이며 공식 제공 영문 서지·초록이 모두 갖춰진 참증과 구분하는 상태다.

## 확인 사례

2026-10-21 KR200355113Y1: 첫 English 요청은 과부하, 한 차례 재시도는 정상 번역.
서지 AI 보완·사이트 기계번역 초록·대표도면 1페이지 + 공식 전문 5페이지 = 6페이지 검수 완료.
KPA에는 해당 번호 검색결과가 없었다. 다른 KR 실용신안도 항상 번역/원문이 제공된다고 일반화하지 않는다.
