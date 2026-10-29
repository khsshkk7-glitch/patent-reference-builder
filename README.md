# patent-reference-builder · 특허 참증 PDF 제작 스킬

**v1.0.1** — 2026-10-29 · [변경 이력](CHANGELOG.md) · [첫 정식 릴리스 v1.0.0](https://github.com/khsshkk7-glitch/patent-reference-builder/releases/tag/v1.0.0)

특허번호를 채팅이나 엑셀로 전달하면 **영문 서지사항·영문 초록 → 동일 공보 원문 전문** 순서로 병합하는 Codex 스킬입니다. 최종 PDF는 특허번호를 파일명으로 사용해 사용자의 **다운로드 폴더**에 저장합니다.

주 수집원은 Espacenet이며, 한국 문헌은 KIPRIS를 보조 수집원으로 사용합니다. 원문 다운로드에는 공식 EPO OPS API를 우선 사용합니다. API 키를 사용자 환경변수에 한 번 저장하면 정상 실행에서 매번 입력할 필요가 없습니다.

> **자동화 범위:** OPS로 시험한 JP 두 문헌은 원문 다운로드에 보안문자 입력이 필요 없었습니다. 서지 화면·전문 뷰어는 여전히 브라우저에서 확인하며, 이미지형 표지 식별·번역 보완·최종 시각 검수는 Codex 또는 검수자가 수행합니다. 모든 문헌의 완전 무인 처리를 보장하는 프로그램은 아닙니다.

## 목차

- [1. 만드는 자료](#output)
- [2. 준비물과 처음 사용하는 순서](#start)
- [3. Windows 설치 방법](#install)
- [4. EPO 가입·승인·API 키 발급](#api)
- [5. 키를 한 번 저장하고 계속 사용하기](#credentials)
- [6. Codex 채팅에서 사용하기](#chat)
- [7. 명령으로 직접 실행하기](#cli)
- [8. 엑셀·CSV 작성 방법](#excel)
- [9. 결과 파일과 검수 상태](#results)
- [10. 오류 해결과 자주 묻는 질문](#troubleshooting)
- [11. 업데이트 방법](#update)
- [12. 실제 검증 범위와 개발자 확인](#validation)
- [13. 상세 문서·공식 자료](#references)

<a id="output"></a>
## 1. 만드는 자료

```text
JP 2006-198019 A.pdf
├─ 앞부분: 동일 공보의 영문 서지사항 + 영문 초록
└─ 뒷부분: 동일 공보의 공식 원문 전체
           명세서 + 청구범위 + 도면 + 나머지 공보 페이지
```

| 구성 | 처리 방법 |
|---|---|
| 영문 서지·초록 | Espacenet Bibliographic data 또는 KIPRIS KPA 인쇄 화면을 A4 PDF로 저장 |
| 공식 원문 | 동일 공보번호·종별의 전문을 OPS 또는 공식 사이트에서 수신 |
| 병합 | 영문 서지·초록을 먼저, 공식 원문 전 페이지를 뒤에 배치 |
| 결과표 | 입력 행별 상태·파일명·페이지 수·출처·사유를 XLSX/JSON으로 기록 |
| 검수 | 번호·종별·인명·영문 자료 유형·전체 페이지·도면·잘림 확인 |

OPS 원문은 **공식 단일 페이지 PDF들을 순서대로 조립한 전문**입니다. 브라우저에서 받은 단일 PDF와 바이트가 동일하다고 주장하지 않습니다. API 총 페이지 수와 사이트 전문 뷰어 총 페이지 수를 대조합니다.

등록번호로 영문 초록을 찾지 못하면 먼저 같은 출원의 공개번호로 KPA를 재검색합니다. 공개공보 영문 초록이 있으면 출처 공개번호를 앞장에 밝히고 요청한 등록공보 원문과 결합합니다. 출원번호가 다른 자료는 사용하지 않습니다.

공개번호 재검색에서도 영문 초록을 찾지 못하면 동일 공보의 사이트 기계번역을 확인합니다. 사용할 수 없으면 Codex가 원문 초록을 읽어 AI 번역하며, 원문에도 초록이 없을 때만 확인한 명세서 부분에서 AI 요약을 작성합니다. 번역·요약 고지를 붙여 **공식 제공 영문 초록과 구분**합니다.

<a id="start"></a>
## 2. 준비물과 처음 사용하는 순서

```text
스킬 설치 → Python 의존성·브라우저 준비 → EPO OPS 가입
→ 승인 확인 → 앱 생성·키 발급 → 사용자 환경변수 저장
→ Codex 재시작 → 특허번호 또는 엑셀로 참증 요청
```

| 준비물 | 용도 |
|---|---|
| 로컬 파일·프로그램 실행이 가능한 Codex 환경 | 스킬 호출, 자료 검토, 번역 보완·최종 검수 |
| Windows와 Google Chrome | 이 저장소에서 주로 실사이트 검증한 실행 환경 |
| Python 3.10 이상 | PDF·엑셀 처리 및 수집 스크립트 실행 |
| Git | 저장소 설치·업데이트. 없으면 ZIP 설치 가능 |
| EPO OPS 개발자 계정과 앱의 Key/Secret | 기본 OPS 원문 다운로드 |
| 인터넷 연결·저장 권한 | 공식 사이트 접속 및 다운로드 폴더 저장 |

Python은 [공식 다운로드](https://www.python.org/downloads/windows/), Git은 [공식 설치 안내](https://git-scm.com/install/windows), Chrome은 [공식 다운로드](https://www.google.com/chrome/)에서 준비할 수 있습니다.

**이미 설치했다면 재설치하지 말고 [업데이트](#update) 항목을 보세요.** 정상 저장된 키도 다시 등록할 필요가 없습니다.

<a id="install"></a>
## 3. Windows 설치 방법

### 3-1. Codex에 설치를 요청하기

Codex 채팅에서 다음처럼 요청할 수 있습니다.

```text
https://github.com/khsshkk7-glitch/patent-reference-builder
이 저장소 루트를 patent-reference-builder 스킬로 설치하고,
Python 가상환경·requirements.txt·Playwright 브라우저까지 준비해줘.
이미 설치돼 있으면 기존 위치와 변경사항부터 확인해줘.
```

설치 중 로컬 파일 쓰기·네트워크·브라우저 실행에 대한 환경의 승인 절차가 표시될 수 있습니다. EPO 계정 가입과 키 등록은 아래 별도 절차를 따릅니다.

### 3-2. PowerShell에서 직접 설치하기

새 설치 위치는 현재 [OpenAI 공식 스킬 안내](https://learn.chatgpt.com/docs/build-skills)의 `~/.agents/skills`를 기준으로 설명합니다. 기존 `~/.codex/skills/patent-reference-builder`에 설치해 사용 중이라면 **그 위치를 그대로 사용**하세요. 같은 스킬을 두 경로에 중복 설치하지 않습니다.

PowerShell을 열고 실행합니다. `$skillDir`은 설치 폴더를 가리키는 변수입니다.

```powershell
$skillDir = Join-Path $env:USERPROFILE '.agents\skills\patent-reference-builder'
New-Item -ItemType Directory -Force -Path (Split-Path $skillDir) | Out-Null
git clone https://github.com/khsshkk7-glitch/patent-reference-builder.git $skillDir
Set-Location $skillDir
```

`destination path already exists`가 나오면 폴더를 삭제하거나 덮어쓰지 말고 기존 설치 여부를 확인합니다. ZIP 설치는 GitHub의 **Code → Download ZIP**으로 내려받아 압축을 풀고 폴더 이름을 `patent-reference-builder`로 맞춥니다.

설치 폴더 바로 아래에 다음 파일들이 있어야 합니다. 압축을 풀면서 같은 이름의 폴더가 한 겹 더 생기지 않았는지 확인하세요.

```text
patent-reference-builder/
├─ SKILL.md
├─ README.md
├─ requirements.txt
├─ agents/
├─ scripts/
└─ references/
```

### 3-3. Python 실행 환경 만들기

**이후 PowerShell 명령은 모두 설치 폴더에서 실행합니다.** Python 버전을 확인한 뒤 가상환경과 의존성을 준비합니다.

```powershell
py --version
py -3 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m playwright install chromium
```

`py`를 찾지 못하고 `python --version`은 정상 동작하면 첫 두 줄 대신 `python --version`, `python -m venv .venv`를 사용합니다. 버전은 3.10 이상이어야 합니다.

가상환경 활성화 명령은 필요 없습니다. 문서처럼 `.venv` 안의 Python을 직접 실행하면 PowerShell의 활성화 스크립트 실행 정책을 바꾸지 않아도 됩니다.

Playwright Chromium과 **설치된 일반 Google Chrome은 별개**입니다. 기본 명령의 `--native-chrome`은 일반 Chrome을 별도 작업용 프로필로 열기 때문에 Chrome도 설치돼 있어야 합니다. 평소 Chrome 프로필을 바꾸지 않습니다.

### 3-4. 설치 확인

다음 명령은 실제 사이트 접속·공보 다운로드 없이 옵션과 입력번호를 확인합니다.

```powershell
& .\.venv\Scripts\python.exe scripts/build_references.py --help
& .\.venv\Scripts\python.exe scripts/build_references.py --text "JP 2006-198019 A" --dry-run --out output/installation-check
```

`output/installation-check/input-plan.json`에서 정규화 번호와 `pn=JP2006198019A` 검색 쿼리를 확인합니다. **dry-run 성공은 사이트 수집·API 인증 성공이 아닙니다.**

설치한 스킬이 보이지 않으면 Codex를 재시작하고 새 대화에서 `$patent-reference-builder`로 호출합니다.

<a id="api"></a>
## 4. EPO 가입·승인·API 키 발급

### 4-1. 필요한 계정과 무료 범위

필요한 것은 **EPO OPS 개발자 포털 계정과 앱 인증정보**입니다. 일반 EPO 서비스 계정에 가입한 것만으로 이 설정이 끝난 것은 아닙니다. [EPO OPS 공식 안내](https://www.epo.org/en/searching-for-patents/data/web-services/ops)에서 서비스를 확인할 수 있습니다.

2026-10-24 확인한 공식 안내에서 **Non-paying은 주 4GB까지 무료**입니다. 한도를 넘는 이용은 별도 유료 조건이 있으므로 실제 신청 화면과 최신 약관을 확인하세요. 이 스킬은 유료 가입을 자동 신청하지 않습니다.

### 4-2. 개발자 계정 신청

1. [EPO 개발자 등록 화면](https://developers.epo.org/user/register)을 엽니다.
2. 사용자명·이메일·비밀번호, 본인·회사·연락처 정보를 실제 내용대로 입력합니다.
3. 무료 범위로 이용하려면 **Account Type → Non-paying**을 선택합니다.
4. **What do you need OPS for?**는 실제 목적에 맞게 고릅니다. 회사 내부 참증 업무라면 `Building/enriching in-house database(s) for internal use` 항목이 목적에 맞는지 확인해 선택할 수 있습니다. 회사 구분·직무도 실제 내용에 맞춰 입력합니다.
5. 약관·회사 대리 권한 확인·가입 보안문자를 직접 처리하고 신청합니다.

가입 이메일에 `Your registration details are now being validated`라고 쓰여 있으면 **접수 후 확인 중**이라는 뜻입니다. 승인 완료로 해석하지 않습니다. 별도 승인·활성화 안내를 확인하고 스팸함도 살펴보세요. 승인 소요 시간은 이 저장소에서 보장하지 않습니다.

### 4-3. 승인 후 앱 생성

1. [개발자 포털 로그인](https://developers.epo.org/user/login)
2. **My Apps** 선택
3. **Add a new App** 선택
4. **App Name**에 `patent-reference-builder` 입력
5. **Create App**으로 생성
6. 생성된 앱 상세 화면에서 **Consumer Key**와 **Consumer Secret** 확인

| 앱 화면의 값 | 사용자 환경변수 이름 |
|---|---|
| Consumer Key | `EPO_OPS_KEY` |
| Consumer Secret | `EPO_OPS_SECRET` |

이 값은 포털 비밀번호나 일시적인 Access Token과 다릅니다. 스크립트가 Key/Secret으로 Access Token을 받아 사용하므로 토큰을 직접 저장할 필요는 없습니다. 발급 흐름은 [EPO OPS 공식 매뉴얼의 등록·인증 부분](https://link.epo.org/web/searching-for-patents/data/en-ops-v3.2-documentation-version-1.3.20.pdf)도 참고할 수 있습니다.

**실제 Key/Secret이나 값이 보이는 스크린샷을 채팅·GitHub 이슈에 올리지 마세요.** 로컬 설정 창에서 직접 입력합니다.

<a id="credentials"></a>
## 5. 키를 한 번 저장하고 계속 사용하기

### 5-1. 기본 방식: Windows 사용자 환경변수

설치 폴더의 PowerShell에서 로컬 입력 창을 엽니다.

```powershell
& .\.venv\Scripts\pythonw.exe scripts/ops_environment.py --setup
```

1. 첫 칸에 **Consumer Key**, 둘째 칸에 **Consumer Secret**을 붙여넣습니다.
2. 입력값은 `***`로 표시됩니다. 기존 저장값은 표시하지 않습니다.
3. **Windows 사용자 환경변수에 저장**을 누릅니다. 기존 두 값이 있으면 교체됩니다.
4. 저장 완료를 확인한 뒤 **Codex와 기존 PowerShell 창을 완전히 종료**합니다.
5. Codex 또는 새 PowerShell을 다시 열어 사용합니다.

등록 도우미는 현재 사용자의 두 환경변수만 설정합니다. 별도 TXT·로그 파일에 키를 쓰지 않습니다. 다만 **환경변수 자체는 암호화 보관소가 아니며 같은 사용자 권한의 프로그램이 읽을 수 있습니다.**

### 5-2. 적용 여부 확인

새 PowerShell에서 설치 폴더로 이동한 뒤 실행합니다.

```powershell
& .\.venv\Scripts\python.exe scripts/ops_environment.py --status
```

다음은 예시 출력입니다. 실제 키 값은 출력하지 않습니다.

```json
{
  "process": {"EPO_OPS_KEY": true, "EPO_OPS_SECRET": true},
  "windows_user": {"EPO_OPS_KEY": true, "EPO_OPS_SECRET": true}
}
```

| 상태 | 다음 행동 |
|---|---|
| 두 값 모두 `process=true` | 현재 실행이 값을 사용할 수 있음. 재입력 없이 실행 |
| `windows_user=true`, `process=false` | 저장됐지만 기존 실행에는 미반영. Codex·터미널 완전 종료 후 다시 열기 |
| 사용자 환경에도 하나 이상 없음 | `--setup`으로 두 값 등록 후 재시작 |
| 재시작했는데 계속 현재 프로세스에 없음 | 실제 사용자 계정·실행 환경 확인. 필요하면 Windows 로그아웃 후 로그인 |

제한된 실행 계정이나 별도 샌드박스는 다른 사용자 환경을 볼 수 있습니다. 정상 사용자 세션의 결과와 구분하세요. **`true`는 값이 존재한다는 뜻이지 EPO 인증 성공을 보장하지는 않습니다.**

### 5-3. 영구 저장 없이 이번 실행만 사용

사용자 환경변수로 저장하고 싶지 않으면 로컬 터미널에서 다음 도우미를 실행합니다. 없는 값만 숨김 입력을 요청하며 이 도우미 자체는 영구 저장하지 않습니다.

```powershell
& .\.venv\Scripts\python.exe scripts/run_with_ops.py --text "JP 2006-198019 A" --native-chrome --headed --zip
```

환경변수 방식으로 이미 설정했다면 매번 이 입력 절차를 할 필요가 없습니다. 인증 오류 때의 수정은 [문제 해결](#troubleshooting)을 보세요.

<a id="chat"></a>
## 6. Codex 채팅에서 사용하기

설치·키 저장 후에는 평소 아래처럼 요청하면 됩니다. 실제 Key/Secret은 요청문에 넣지 않습니다.

### 단건·다건 요청

```text
$patent-reference-builder
JP 2006-198019 A 참증 만들어줘.
저장된 OPS 환경변수를 사용하고 최종 검수까지 진행해줘.
```

```text
$patent-reference-builder
아래 두 문헌 참증을 만들어줘.
JP 2006-198019 A
JP 2004-121879 A
다운로드 폴더에 저장하고 검수 완료 자료를 ZIP으로 묶어줘.
```

### 엑셀·CSV 첨부 또는 경로 전달

```text
$patent-reference-builder
첨부한 엑셀의 전체 특허번호를 처리해줘.
실패·제외된 행도 결과표에 남기고,
공식 영문 자료와 AI 번역 보완 자료를 구분해 최종 검수까지 진행해줘.
```

```text
$patent-reference-builder
"C:/Users/사용자명/Desktop/참증목록.xlsx"에 있는 문헌을 처리해줘.
```

경로는 Codex가 접근할 수 있는 실제 파일 위치로 바꿉니다.

### KIPRIS에서만 직접 수집

```text
$patent-reference-builder
KR 10-2020-0137353을 KIPRIS만 사용해서 참증 만들어줘.
다른 사이트로 대체하지 말고 실패 원인을 기록해줘.
```

Codex는 입력번호 확인·수집에 이어 스캔 식별, 원문 기반 번역 보완, 최종 시각 검수를 수행합니다. **Python 명령만 실행하는 것과 이 검토 과정까지 수행하는 것은 다릅니다.**

<a id="cli"></a>
## 7. 명령으로 직접 실행하기

모든 예시는 설치 폴더의 PowerShell 기준입니다. 경로에 공백이 있으면 따옴표로 감쌉니다. 기본 저장 위치는 다운로드 폴더이므로 다른 위치를 원할 때만 `--out`을 지정합니다.

### 입력번호만 먼저 확인

```powershell
& .\.venv\Scripts\python.exe scripts/build_references.py --text "KR 10-2020-0137353, JP 2006-198019 A" --dry-run --out output/input-check
```

### 저장된 키로 단건·다건 실행

```powershell
& .\.venv\Scripts\python.exe scripts/build_references.py --text "JP 2006-198019 A" --original-method ops --native-chrome --headed --zip
```

```powershell
& .\.venv\Scripts\python.exe scripts/build_references.py --text "JP 2006-198019 A, JP 2004-121879 A" --original-method ops --native-chrome --headed --zip
```

### 엑셀·CSV 배치

```powershell
& .\.venv\Scripts\python.exe scripts/build_references.py --input "C:/업무/참증목록.xlsx" --original-method ops --native-chrome --headed --zip
```

특정 시트·컬럼을 지정할 때:

```powershell
& .\.venv\Scripts\python.exe scripts/build_references.py --input "C:/업무/참증목록.xlsx" --sheet "Sheet1" --column "공개번호" --original-method ops --native-chrome --headed
```

CSV에는 시트가 없으므로 `--sheet`를 생략합니다.

```powershell
& .\.venv\Scripts\python.exe scripts/build_references.py --input "C:/업무/참증목록.csv" --column "공개번호" --original-method ops --native-chrome --headed --zip
```

### 다른 폴더에 저장

```powershell
& .\.venv\Scripts\python.exe scripts/build_references.py --text "JP 2006-198019 A" --original-method ops --native-chrome --headed --out "C:/업무/참증결과" --zip
```

### KIPRIS 직접 수집

```powershell
& .\.venv\Scripts\python.exe scripts/build_references.py --text "KR20200137353A" --source kipris --native-chrome --headed --no-fallback --zip
```

`--no-fallback`은 KIPRIS에서 실패해도 Espacenet으로 대체하지 않는 옵션입니다. **이 명령에 `--original-method ops`를 함께 지정하지 않습니다.** OPS는 Espacenet 원문용입니다.

### API 대신 브라우저 다운로드 선택

키가 없거나 사용자가 브라우저 방식을 선택하면 다음처럼 명시합니다.

```powershell
& .\.venv\Scripts\python.exe scripts/build_references.py --text "JP 2006-198019 A" --original-method browser --native-chrome --headed --interactive --human-timeout 300
```

보안문자가 나오면 열린 Chrome에서 직접 숫자를 입력하고 **Submit**을 누릅니다. 파일 수신 후 자동 진행하므로 다운로드 단계에서는 터미널 Enter가 필요 없습니다. 반복 인증은 계속 풀도록 요구하지 않고 중단·진단합니다.

### 주요 옵션

| 옵션 | 의미 |
|---|---|
| `--text` / `--input` | 번호 문자열 / XLSX·XLS·CSV. 둘 중 하나 지정 |
| `--original-method ops` | 스킬 기본 운영. 저장된 키로 OPS 사용, 누락 시 설정 안내 |
| `--original-method browser` | 공식 사이트 다운로드와 사용자 보안문자 입력 |
| `--original-method auto` | CLI 기본값. 키가 있으면 OPS, 없으면 브라우저 |
| `--source kipris --no-fallback` | KR을 KIPRIS에서만 수집 |
| `--native-chrome --headed` | 별도 프로필로 일반 Chrome 열기 |
| `--column`, `--sheet` | 번호 컬럼·엑셀 대상 시트 지정 |
| `--role application` | 출원번호로 취급. 대응 공보 매핑 검토 후 재개 필요 |
| `--role publication` | 공보번호로 명시. 헤더와 충돌하면 실패 기록 |
| `--out` | 다운로드 폴더 대신 지정 위치 사용 |
| `--zip` | 생성 자료·결과표를 검수 대기 ZIP으로 묶기 |
| `--dry-run` | 검색·다운로드 없이 전체 입력 계획·행별 오류 확인 |
| `--original-only` | 공식 원문만 수집. 완성 참증으로 집계하지 않음 |

**스킬 지침의 기본 선택은 `ops`, 일반 CLI 기본값은 `auto`입니다.** 직접 실행하면서 키 누락 시 브라우저 전환을 원하지 않으면 예시처럼 `--original-method ops`를 넣습니다.

<a id="excel"></a>
## 8. 엑셀·CSV 작성 방법

한 행에 한 문헌을 넣습니다. 다음처럼 작성할 수 있습니다.

| 관리번호 | 공개번호 | 메모 |
|---|---|---|
| 1 | JP 2006-198019 A | 일본 공개공보 |
| 2 | JP 2004-121879 A | 일본 공개공보 |
| 3 | KR 10-2020-0137353 A | 한국 공개공보 |
| 4 | KR 20-2007-0000036 U | 실용신안. 영문 보완이 필요할 수 있음 |

- `특허번호`, `공보번호`, `공개번호`, `출원번호`, `Patent No.`, `Publication No.` 등의 헤더를 탐지합니다. 헤더가 없으면 유효 번호 패턴 컬럼을 찾습니다.
- 여러 번호 컬럼이 있으면 `--column`으로 지정합니다. 시트는 기본적으로 전체를 읽으며 `--sheet`로 제한할 수 있습니다.
- `.xlsx`는 openpyxl, `.xls`는 pandas/xlrd로 읽습니다. CSV는 UTF-8 BOM/CP949 및 쉼표·탭·세미콜론 구분을 지원합니다.
- 빈 번호·잘못된 번호 데이터행도 실패 사유를 남깁니다. 완전히 빈 행·확인된 헤더는 문헌 건수에서 제외합니다.
- 중복 문헌은 행별 기록하되 같은 실행 내 PDF를 재사용할 수 있습니다.
- 원본은 수정하지 않습니다. 결과 엑셀은 원본 시트·행의 **값 중심 복사본**이며 서식·차트·매크로를 복제하지 않습니다. 수식은 실행되지 않는 텍스트로 보존합니다.

**출원번호와 공개·등록공보 번호는 다릅니다.** 출원번호 헤더나 `--role application`은 대응 공보를 임의 선택하지 않고 매핑 검토를 요구합니다. 공보번호 작업에는 정확한 공개·등록번호와 종별을 사용하세요.

`KR1020200137353A`, `KR 10-2020-0137353 A`, `JP 2006-198019 A`, `特開2006-198019` 등을 정규화합니다. A/B/U/Y를 임의로 바꾸지 않습니다. 종류가 없고 같은 번호에 여러 공보가 가능하면 확인이 필요합니다. 일본 연호 등 미지원 표기는 확인된 서력 번호로 바꿉니다. 한국 실용신안의 10/20 구분은 [한국 번호 정규화](references/kr-numbering.md)를 참고하세요.

<a id="results"></a>
## 9. 결과 파일과 검수 상태

### 저장 위치·파일명

`--out`을 생략하면 OS에 등록된 사용자 다운로드 폴더에 저장합니다. Windows에서 다운로드 위치를 변경했다면 그 위치를 반영합니다.

```text
다운로드 폴더/
├─ JP 2006-198019 A.pdf
├─ KR 10-2020-0137353.pdf
├─ 처리결과_실행ID.xlsx
├─ 처리결과_실행ID.json
├─ 검수대기_실행ID.zip                # --zip 지정 시
├─ 검수결과_검수ID.xlsx               # 검수 적용 후
├─ 검수결과_검수ID.json
├─ 검수완료자료_검수ID.zip            # 승인 자료가 있을 때
└─ work/실행ID/                      # 원본 조각·출처·해시·검수 패킷
```

기존 PDF는 덮어쓰지 않습니다. 같은 이름이 있으면 `(2)`, `(3)`처럼 순번을 붙입니다. 실제 파일명·절대 경로는 결과표·JSON에서 확인합니다. 검수 재개에 필요한 원본 조각·이미지가 있으므로 `work`를 보존하세요.

### 생성 완료와 검수 완료 구분

| 표시 | 의미 |
|---|---|
| `생성 완료` / `검수 대기` | 병합 완료, 최종 시각 검수 미완료 |
| `원문 식별 검수 대기` | 원문은 확보했지만 스캔 등으로 표지 번호·종별 자동 판독 불가. 대조 후 재개 |
| `번역 검토 대기` | 원문은 확보했지만 영문 보완 필요. Codex가 원문을 읽고 번역·대조 후 재개 |
| `AI 번역 보완` / `사이트 기계번역 보완` | 고지가 있는 보완자료. 공식 제공 영문 초록과 구분 |
| `검수 완료` | 해당 자료 유형의 최종 PDF 검토를 마치고 근거 적용 |
| `실패` / `제외` | 오류 또는 대상 제외. 사유 확인 필요 |

`complete_reference=true`는 공식 영문 구성자료를 갖추고 최종 검수까지 완료한 경우입니다. AI·사이트 번역·원문 단독은 검수 후에도 이 값이 `false`이며, `final_review_complete`로 해당 유형의 검수 완료 여부를 확인합니다.

`검수대기_*.zip`은 제출 준비 완료를 뜻하지 않습니다. [최종 검수 절차](references/final-review.md)로 승인한 PDF만 `검수완료자료_*.zip`에 들어갑니다. Python은 이미지와 검수 근거를 연결하지만 이미지 생성만으로 승인하지 않습니다.

| 생성 명령 종료코드 | 의미 |
|---|---|
| `0` | 전건 생성 완료. 최종 시각 검수는 별도 |
| `1` | 일부/전체 실패 또는 식별·번역 검토 대기 |
| `2` | 잘못된 옵션, 입력·출력 또는 실행 설정 오류 |

<a id="troubleshooting"></a>
## 10. 오류 해결과 자주 묻는 질문

| 현상 | 확인·해결 순서 |
|---|---|
| `python`, `py`를 못 찾음 | Python 설치·버전 확인 후 새 PowerShell 열기. `py` 대신 `python` 가능 여부 확인 |
| `ModuleNotFoundError` | `.venv\Scripts\python.exe -m pip install -r requirements.txt` 실행. 다른 Python으로 실행했는지 확인 |
| Playwright 브라우저 실행 파일 없음 | `.venv\Scripts\python.exe -m playwright install chromium` 실행 |
| 일반 Chrome을 못 찾음 | Google Chrome 설치 확인. `--native-chrome`에는 일반 Chrome이 별도 필요 |
| OPS 키 미설정 | `ops_environment.py --status`로 존재 여부만 확인. 없으면 `--setup`, 저장돼 있는데 현재 실행에 없으면 재시작 |
| OPS 인증 단계 HTTP 400/401 | 앱의 현재 Key/Secret과 로컬 설정 확인. 필요하면 `--setup`으로 두 값 교체 후 재시작 |
| OPS HTTP 403 | 계정 승인·앱 API 권한·서비스 조건 확인. 잘못된 키로 단정하지 않음 |
| OPS HTTP 429 | 이용량·속도 제한 확인. 키 재입력·무한 재시도하지 않음 |
| 5xx·네트워크 오류 | 서비스·네트워크 상태 확인. 이 오류만으로 키를 교체하지 않음 |
| 원문을 받았는데 식별 검수 대기 | 이미지형 표지일 수 있음. `identity-review.json`의 원문을 대조하고 manifest로 재개. 키 재입력·반복 다운로드 불필요 |
| Submit 후 다시 보안문자 | 반복 감지 시 중단. 계속 입력하거나 자동 해독하지 않음. [브라우저 복구](references/browser-recovery.md) 참고 |
| KIPRIS 상세가 오류 화면으로 이동 | `--native-chrome --headed` 확인. KIPRIS 직접 시험은 `--source kipris --no-fallback` 사용 |
| 등록번호의 KPA 영어 결과가 없음 | 같은 출원의 공개번호로 KPA 재검색. 공개공보 영문 초록의 출처를 밝히고 등록공보 원문 유지. 재검색도 실패하면 원문 기반 번역 보완 |
| 출력 폴더 하드 링크 생성 오류 | 안전한 최종 파일 저장 단계. 로컬 NTFS 등 지원 폴더를 `--out`으로 지정 |
| 결과에 빈 번호·제외 행이 있음 | 행별 사유와 `input-accounting.json`의 입력·기록·제외·실패 수 확인 |

### 키는 매번 입력하나요?

사용자 환경변수에 등록하고 새 실행에 적용됐다면 다시 입력하지 않습니다. 없는 경우나 실제 인증정보 수정이 필요한 경우에만 로컬 설정 창을 안내합니다. `--status`의 존재 여부와 실제 API 인증 성공은 다릅니다.

### 자동화인데 왜 검토 대기가 나오나요?

스캔 표지의 번호·종별을 못 읽거나 영문 초록이 없으면 잘못된 문헌을 성공 처리하지 않도록 대기합니다. Codex가 실제 파일을 확인해 복구 절차로 이어가며, 해당 파일을 다시 받거나 보안문자를 반복 입력할 필요는 없습니다.

### Codex 없이 Python만 실행해도 번역·검수가 끝나나요?

아닙니다. Python은 사이트 수집·PDF 생성·결과 기록과 검수 근거 검증을 수행합니다. AI 번역·원문 대조·시각 검수는 Codex 또는 사람이 수행하며, 검토 manifest와 최종 검수 기록으로 연결합니다.

### 어떻게 복구를 요청하나요?

```text
$patent-reference-builder
OPS 연결이 안 돼. 키 값은 출력하지 말고 설정 여부부터 확인해줘.
저장된 환경변수와 현재 실행 적용 여부를 구분하고,
값이 없거나 인증정보 수정이 필요하면 로컬 숨김 설정 창을 안내해줘.
```

스캔·번역 대기는 [검토 후 재개](references/browser-recovery.md), [AI 보완 작성](references/ai-fallback.md)을 따릅니다. 실제 확인 없이 검수 플래그를 `true`로 바꾸지 않습니다.

### 오류를 GitHub에 올릴 때는?

공보번호, 실행 옵션, 민감정보를 제거한 오류 메시지, 발생 단계와 기대 결과를 남깁니다. 실제 키·Authorization·토큰은 올리지 않습니다. 업무 원문·엑셀·개인정보가 있는 화면도 공개 저장소에 자동 업로드하지 않습니다.

<a id="update"></a>
## 11. 업데이트 방법

**현재 실제 설치 폴더에서** 실행합니다. 기존 `.codex/skills` 설치를 업데이트하려고 `.agents/skills`에 중복 복사본을 만들지 마세요.

```powershell
git status --short
git pull --ff-only
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m playwright install chromium
```

첫 명령에 본인이 수정한 파일이 나오면 변경사항을 먼저 보존·검토합니다. 오류 해결을 위해 임의 초기화·덮어쓰기를 하지 않습니다. ZIP 설치는 로컬 변경과 업무 자료를 보존한 뒤 배포 파일을 갱신합니다.

스킬 변경이 안 보이면 Codex를 재시작합니다. 사용자 환경변수는 저장소 밖의 설정이므로 일반 코드 업데이트 때 키를 다시 입력할 필요는 없습니다.

<a id="validation"></a>
## 12. 실제 검증 범위와 개발자 확인

2026-10-23에 확인한 주요 실제 수집 결과입니다. 표본 통과가 모든 국가·종별의 지원을 보장하지는 않습니다.

| 문헌 | 확인한 결과 |
|---|---|
| JP 2006-198019 A | OPS 원문 9페이지, 식별 검토 재개 후 영문 서지 1 + 원문 9 = 10페이지 최종 검수 |
| JP 2004-121879 A | 같은 다건 실행의 OPS 원문 12페이지, 검토 재개 후 총 13페이지 최종 검수 |
| KR 10-2020-0137353 A | KIPRIS 직접 수집, KPA 1 + 원문 19 = 20페이지 검수 |
| KR 20-2007-0000036 U | KIPRIS 원문 6페이지, Codex AI 번역 보완 후 총 7페이지 검수. 공식 영어 초록으로 표시하지 않음 |

OPS JP 두 건은 원문 수신 중 사용자 보안문자 입력이 없었습니다. 표지 문자는 자동으로 읽히지 않아 Codex가 실제 페이지를 확인했습니다. [검증 기록](references/validation.md)에 수신·식별·생성·최종 검수를 구분해 남깁니다.

최근 코드 변경 검증은 자동 테스트 **144개 중 143개 통과, 개인 샘플을 별도 지정해야 하는 1개 생략**입니다. 모의 응답·합성 PDF와 실제 사이트 검증은 구분합니다.

개발자 회귀 테스트:

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
& .\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

실제 API 키 없이 실행 가능한 테스트를 포함합니다. 자동 테스트 통과만으로 최신 사이트의 모든 다운로드가 성공했다고 판단하지 않습니다.

Windows가 주 검증 환경입니다. macOS/Linux는 가상환경 Python 경로가 `.venv/bin/python`으로 다르며 Windows 환경변수 저장 창은 사용할 수 없습니다. 이 문서의 Windows 실수집 결과를 다른 OS 검증 결과로 해석하지 않습니다.

<a id="references"></a>
## 13. 상세 문서·공식 자료

| 문서 | 확인할 때 |
|---|---|
| [SKILL.md](SKILL.md) | Codex가 따르는 전체 작업 지침 |
| [실행 방법](references/usage.md) | 추가 옵션·브라우저 연결·입출력 규칙 |
| [OPS 설정](references/ops-setup.md) | 발급·환경변수·인증 복구·지원 범위 |
| [브라우저 복구·검토 manifest](references/browser-recovery.md) | 접근 제한·스캔 식별·로컬 자료로 재개 |
| [최종 검수](references/final-review.md) | 이미지 확인·승인·반려·결과표·완료 ZIP |
| [AI 번역·요약 보완](references/ai-fallback.md) | 공식 영어 자료가 없는 문헌 |
| [사이트 기계번역](references/patent-translate.md) | Patent Translate 확인·고지 보존 |
| [한국 번호 정규화](references/kr-numbering.md) | 특허/실용신안·10/20·공보/출원 구분 |
| [검증 기록](references/validation.md) | 실제 검증한 표본과 제한 |

공식 서비스·계정 정보:

- [Espacenet 검색](https://worldwide.espacenet.com/advancedSearch?locale=en_EP)
- [KIPRIS 검색](https://www.kipris.or.kr/khome/search/searchResult.do?tab=patent)
- [EPO OPS 서비스·무료 한도](https://www.epo.org/en/searching-for-patents/data/web-services/ops)
- [EPO 개발자 등록](https://developers.epo.org/user/register) · [로그인](https://developers.epo.org/user/login)
- [EPO OPS 공식 매뉴얼](https://link.epo.org/web/searching-for-patents/data/en-ops-v3.2-documentation-version-1.3.20.pdf)
- [OpenAI 공식 스킬 안내](https://learn.chatgpt.com/docs/build-skills)

가입·한도 안내 확인일은 **2026-10-24**입니다. 사이트 정책·화면·요금은 바뀔 수 있으므로 실제 신청·사용에는 공식 사이트의 현재 조건을 확인하세요.
