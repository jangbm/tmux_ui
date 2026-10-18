# tmux Workspace

Textual 기반 프로젝트·Claude/Codex 작업 화면입니다. UI는 별도 `tmux-ui-preview` 서버에서 실행하고, 기존 tmux의 원본 AI 화면을 읽습니다. 사용자가 보내기·메뉴 조작을 하거나 메시지를 대기열에 등록한 경우에만 선택한 원본 AI에 입력을 전달합니다.

## 실행과 설치

이 개발 PC:

```bash
cd /home/jang/projects/tmux_ui/workspace
./launch.sh
```

Windows CMD/PowerShell:

```powershell
wsl -d Ubuntu -- bash -lc 'cd /home/jang/projects/tmux_ui/workspace && ./launch.sh'
```

새 환경에서는 Python 가상환경과 등록된 프로젝트가 필요합니다. 현재 검증 환경은 Python 3.14, tmux 3.6, Textual 7.5.0입니다.

```bash
cd workspace
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python core.py add "MyProject" ./data/MyProject --id myproject --git --start
./launch.sh
```

일부 설정(`preview.conf`, Windows 프로필)에 개발 PC의 절대 경로가 있습니다. 다른 PC에서는 경로를 조정해야 합니다. 기존 운영 `~/.tmux.conf`는 설치 과정에서 변경하지 않습니다. `Ctrl+b d`는 UI에서 분리하며 AI를 종료하지 않습니다.

## 프로젝트와 사이드바

- 원본 tmux 서버의 새 세션은 약 8초 주기로 자동 등록됩니다. 처음에는 기본 서버를 발견하며, 등록 후에는 알려진 원본 소켓을 조회합니다.
- 세션 삭제가 정상 조회로 확인되면 사이드바에서 숨깁니다. 서버 접속 오류만으로 프로젝트를 삭제하지 않습니다. 같은 세션이 돌아오면 다시 표시합니다.
- 이름 검색, 전체/작업 중/결과/승인 대기 필터, 현재 프로젝트의 ☆ 상단 고정을 지원합니다.
- 관제에서 만든 AI는 전면 프로세스별로 연결합니다. Claude의 하위 작업 프로세스를 별도의 Codex 창으로 세지 않습니다.
- 프로젝트 클릭은 탭을 열고, 존재하는 Claude/Codex만 표시합니다. AI가 여러 pane에 있으면 전송할 대상을 선택합니다. 원본 pane이 재생성되어 유일한 새 대상이 있으면 화면을 다시 연결하며 기존 예약 전송은 멈춥니다.
- 새 프로젝트 `n`/+, 기존 폴더 등록 `i`. 한글 프로젝트 이름은 허용하지만 수동 등록 ID는 영문/숫자로 지정합니다. 자동 발견한 한글 세션은 안정적인 ID를 생성합니다.

```bash
.venv/bin/python core.py add "프로젝트" /absolute/existing/path --id project --mode import
.venv/bin/python ui-maintenance.py status
.venv/bin/python ui-maintenance.py discover
```

폴더 신뢰 확인은 자동 승인하지 않습니다. 목록 숨기기, AI 종료, 실제 폴더 삭제는 서로 다른 작업입니다.

## 탭과 배치

- 탭 드래그로 순서를 바꾸거나 다른 그룹으로 이동합니다. 내용 영역 가장자리에 놓으면 분할합니다.
- 최대 두 그룹이며 각 그룹에 독립적인 탭 줄이 있습니다. 각 프로젝트에는 연결된 AI 수에 맞는 대화 패널이 있습니다.
- 탭 우클릭/⋯: 고정, 오른쪽·아래 분할, 다른 그룹 이동, 다른 탭 닫기. 다른 탭 닫기는 고정 탭을 유지합니다.
- `Ctrl+PageUp/PageDown`: 이전·다음 탭. 다시 선택한 탭은 최신 내용으로 이동합니다.
- 사이드바 경계, 그룹 경계, Claude/Codex 사이 경계를 드래그하여 크기를 조절합니다.
- 사이드바 하단 ▤/▥로 프로젝트 목록을 위/왼쪽에 배치합니다. 작은 창에서는 일부 버튼과 긴 이름이 잘릴 수 있으므로 넓혀 사용할 수 있습니다.

## 메시지·승인·대기열

- Enter 전송, Shift+Enter 줄바꿈. 입력창은 한 줄에서 최대 네 줄까지 늘어납니다.
- 원본의 흐린 추천은 placeholder로 표시합니다. 빈 입력창에서 Tab으로 가져오며 자동 전송하지 않습니다.
- `/model` 같은 슬래시 명령은 기존 원본 AI에 전달됩니다. 지원 여부는 원본 CLI에 따릅니다.
- 승인 메뉴에서는 해당 AI의 내용창/입력창에 포커스를 두고 방향키·Enter·Esc를 사용합니다. 별도의 선택·취소 버튼도 있습니다.
- Claude의 Shift+Tab/⇧Tab은 준비 상태일 때 원본 모드 전환 키를 보냅니다.
- 작업 중 Enter/+는 다음 메시지를 대기열에 추가합니다. 응답이 끝나 준비 상태가 되면 원래 pane/PID에 전송합니다. 다른 탭으로 이동해도 예약 감시는 유지됩니다.
- 대기열 첫 메시지를 수정·취소할 수 있고 ▶/Ⅱ로 시작·일시정지합니다. 승인 메뉴·원본 초안·연결 변경 시 멈추며 UI 재시작 후에도 일시정지 상태로 복원합니다.
- 전송을 시도했지만 성공 여부가 불분명하면 자동 재전송하지 않습니다. 원본 도착 여부를 확인한 뒤 수정 버튼으로 가져와 처리하세요.
- ■ 또는 선택한 글이 없는 Ctrl+C는 현재 AI의 응답 중지입니다. ×는 대화창 숨기기, ⏻는 대상 확인 후 준비 상태의 AI에 `/exit`를 보내는 종료 기능입니다. tmux pane은 보존합니다.

## 읽기·복사·상태

- 내용 드래그 후 자동 복사, 선택 상태의 Ctrl+C도 복사합니다. 입력창에서 선택한 글 역시 복사를 우선합니다.
- UI의 OSC52 복사가 tmux를 통과하려면 `preview.conf`의 `set -s set-clipboard on`이 필요합니다. Windows `clip.exe`는 추가 경로이며 UTF-16으로 전달합니다.
- Ctrl+F는 **현재 캡처된 화면**의 문자열을 강조합니다. 전체 대화 기록 검색이 아닙니다. Esc로 닫습니다.
- 위를 읽는 동안 최신 내용으로 강제 이동하지 않으며 ↓ 버튼으로 돌아옵니다. 텍스트 선택 중 화면 갱신을 보류합니다.
- 상태는 화면의 입력 프롬프트·승인 선택지·작업 안내로 판정합니다. 흐린 추천은 작성 중인 입력으로 세지 않습니다. 화면 변화에 따라 오판 가능성이 있어 알 수 없는 상태는 전송을 막습니다.
- 결과/승인 대기는 빨간 `결과`로 남습니다. 조회만으로 읽음 처리하지 않으며 새 작업이나 후속 입력으로 해제합니다.
- 활성 대화와 예약 대기열은 0.5초 간격, 전체 상태·프로젝트 발견은 8초 간격으로 조회합니다. 전체 수집에는 0.8초 시간 예산이 있습니다.

## Files · Git · Terminal

- Files는 선택한 프로젝트의 파일을 읽기 전용으로 봅니다. 바이너리·심볼릭 링크·빌드 폴더 등은 제외하고 텍스트 크기를 제한합니다.
- Git은 선택한 프로젝트의 변경 파일, 작업 트리·스테이징 diff, 미푸시/수신 대기 수치를 표시합니다. 미추적 파일 내용은 diff에 포함되지 않습니다.
- 원격 비교 수치는 마지막 fetch 기준입니다. UI가 자동 fetch·commit·push하지 않으며 추적 브랜치가 없으면 미설정으로 표시합니다.
- Terminal에서 Bash/PowerShell/CMD를 선택하여 +로 열고 ×로 숨깁니다. 숨김은 셸 종료가 아닙니다.
- Ctrl+백틱은 하단 터미널 표시/숨김, Ctrl+Shift+백틱은 새 터미널입니다. Windows Terminal에 구분되는 키 시퀀스 설정이 필요할 수 있으며 대체 키는 `Ctrl+b` 다음 `t`입니다. 설정 예시는 `windows-terminal.json`에 있습니다.
- CMD/PowerShell은 WSL interop과 Windows 실행 파일이 필요합니다. 해당 환경이 없으면 사용할 수 없습니다.
- 글꼴과 크기는 Windows Terminal 전체 설정입니다. 중앙 패널만 별도 글꼴 크기를 지정할 수 없습니다.

## 개발·검사·공개 저장소

공동 수정과 UI 갱신 명령은 [CONTROL_UI.md](../CONTROL_UI.md), 점검 우선순위와 결과는 [NOTES.md](../NOTES.md)에 있습니다. 관제와 개발자가 같은 파일을 동시에 덮어쓰지 않도록 조율하세요.

```bash
# 저장소 루트에서 실행
workspace/.venv/bin/python -m unittest discover -s workspace -v
workspace/.venv/bin/python workspace/check-ui-audit.py
workspace/.venv/bin/python workspace/check-session-input.py
workspace/.venv/bin/python workspace/check-clipboard.py
TMW_SOCKET=tmux-ui-test workspace/.venv/bin/python workspace/check-layout.py
TMW_SOCKET=tmux-ui-test workspace/.venv/bin/python workspace/check-status.py
TMW_SOCKET=tmux-ui-test workspace/.venv/bin/python workspace/check-editor-tabs.py
TMW_SOCKET=tmux-ui-test workspace/.venv/bin/python workspace/check-desktop.py
```

통합 검사는 전용 소켓을 사용하고 이미 사용 중인 테스트 서버를 재사용하지 않습니다. Windows interop이 없으면 Windows 셸 검사는 SKIP로 보고합니다. 합성 입력 검사는 Windows의 실제 한글 IME 조합·붙여넣기 종단 검증을 대체하지 않습니다.

`data/`에는 프로젝트 등록, 초안, 예약 메시지, 대화, 재시작 복구 화면이 저장됩니다. 가상환경·환경파일과 함께 Git에서 제외합니다. 원본 대화 캡처·인증정보를 소스/테스트 fixture/공개 문서에 넣지 마세요. `previews/`는 과거 합성 화면 예시이며 최신 화면과 다를 수 있습니다.

## 디자인 점검 캡처

`workspace/.venv/bin/python workspace/capture-design.py after`로 운영 세션에 접속하지 않는 합성 캡처를 생성합니다. 임시 프로젝트와 mock AI 화면만 사용합니다. `previews/design-before-48.svg`와 `design-after-48.svg`는 창 축소 시 입력창 잘림 수정 전후이며, 120열 화면과 승인·사이드바·검색 0건·Files·Git·Terminal 예시도 함께 있습니다. SVG는 브라우저에서 열 수 있고 글꼴에 따라 일부 아이콘 모양이 달라집니다. `before`는 수정 전 소스에서 실행할 때 쓰는 파일 이름입니다.

## 열린 탭과 폴더 탐색

- `Ctrl+P` 또는 탭줄 `⌄`: 모든 그룹의 열린 탭 목록. 이름 검색, ↑↓ 이동, Enter 선택, Esc 취소. 같은 이름의 탭은 그룹 번호로 구분합니다.
- Files의 **펼치기**: 선택 폴더에서 최대 3단계·40폴더를 펼칩니다. **접기**: 선택 폴더와 하위 폴더를 접습니다. 파일을 선택했다면 부모 폴더에 적용합니다.
- 폴더 상태는 프로젝트 경로별로 로컬 저장하여 전환·새로고침·재시작 뒤 복원합니다. Git에는 포함하지 않습니다.
- 트리는 최대 깊이 8, 총 1,000노드, 폴더당 첫 200항목으로 제한합니다. 큰 폴더는 일부 항목이 생략되며 툴팁과 펼치기 알림에서 확인할 수 있습니다. 심볼릭 링크와 생성 폴더는 탐색하지 않습니다.
- `workspace/.venv/bin/python workspace/capture-navigation.py`는 합성 예시만으로 탐색 화면을 캡처합니다. 이전 소스의 workspace 디렉터리를 인자로 주면 before 캡처를 생성합니다.
