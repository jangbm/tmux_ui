# tmux Workspace — 워커용 격리 미리보기

V 드라이브의 tmux-workspace-v3를 바탕으로 한 실행 가능한 시제품입니다.
운영 tmux 설정은 변경하지 않습니다.

## 바로 실행

```bash
cd /home/jang/projects/tmux_ui/workspace
./launch.sh
```

Textual 7.5.0 가상환경과 Git을 초기화한 MyProject 데모가 준비되어 있습니다.
데모 위치는 `workspace/data/MyProject`입니다. `Ctrl+b d`로 미리보기에서 빠져나옵니다.
운영 서버와 별도의 `tmux-ui-preview` 소켓을 사용합니다.

## 새 환경 설치

기본 Python에 ensurepip가 없어 이 PC에서는 uv로 설치했습니다.

```bash
UV_CACHE_DIR=/tmp/tmux-ui-uv-cache uv venv .venv
UV_CACHE_DIR=/tmp/tmux-ui-uv-cache uv pip install --python .venv/bin/python -r requirements.txt
```

## 프로젝트 등록

```bash
# 기존 폴더 등록: 파일을 수정하거나 Git을 초기화하지 않음
.venv/bin/python core.py add "프로젝트" /absolute/existing/path --id project --mode import
# 새 폴더와 Git 저장소 생성: 존재하지 않는 경로 지정
.venv/bin/python core.py add "New Project" ./data/new-project --id new-project --git --start
```

`launch.sh`는 첫 등록 프로젝트로 열립니다. 다른 프로젝트를 바로 열려면:

```bash
.venv/bin/python core.py open project --attach
```

사이드바에서 프로젝트 선택으로 전환, n으로 신규 생성, 마우스로 창 경계 크기 조절이 가능합니다.
AI 창은 기본적으로 셸로 열립니다. 해당 창에서 직접 claude 또는 codex를 실행하세요.
`--launch-agents`는 새 세션을 만들 때만 적용됩니다. 이미 있는 창에는 명령을 주입하지 않습니다.

## 상태와 제한

```bash
./agent-event.sh myproject codex waiting
./agent-event.sh myproject codex done
```

AI 상태는 화면 자동 감지와 수동/외부 이벤트를 함께 사용합니다. 판단할 수 없으면 Unknown입니다.
운영 세션 전체 상태바, Windows 클립보드 연결, 재부팅 복원은 아직 없습니다.
등록부와 상태는 `workspace/data/`에 저장되며 Git 추적에서 제외합니다.

키 입력 주입 및 오류 시 세션 삭제 코드를 제거했습니다. 구성 실패 시 창을 보존하고
불완전한 세션 재사용은 오류로 알려줍니다. 프로그램 종료 시 창도 보존합니다.
세션은 `tw-프로젝트ID`로 생성됩니다. 창 선택은 셸이 바꿀 수 있는 제목 대신 전용 옵션을 사용합니다.

원본 설명은 README.upstream.md를 참고하세요. 원본 설치 명령은 수정본과 다릅니다.

## Graphite 스타일과 글꼴

Cursor의 어두운 편집 화면을 참고해 만든 자체 색상 조합입니다.
배경 #181818, 사이드바 #202020, 본문 #D6D6D6, 선택 강조는 차분한 녹색입니다.
상태는 색 외에도 Working / Waiting / Done 같은 글자로 구분합니다.

Windows Terminal 새 탭 메뉴에서 **Tmux Workspace** 프로필을 선택하세요.
Cascadia Mono 12pt, 줄 높이 1.15, 여백 12/10, 세로 막대 커서를 사용합니다.
Windows Terminal이 새 프로필을 인식하지 않으면 새 터미널 창에서 확인하세요.
글꼴은 터미널 전체에 적용되며 tmux 창마다 다른 글꼴을 지정할 수는 없습니다.
한글 고정폭 글꼴을 선호하면 Windows에 D2Coding을 설치한 뒤 해당 프로필의 글꼴을 변경할 수 있습니다.

프로필 원본: windows-terminal.json.
설치 위치: C:/Users/jang/AppData/Local/Microsoft/Windows Terminal/Fragments/tmux-ui/workspace.json.
기존 settings.json과 기본 프로필은 변경하지 않았습니다.

미리보기의 사이드바 스타일을 다시 불러오려면:

```bash
.venv/bin/python refresh-style.py
```

이 명령은 전용 서버에서 이 프로젝트의 sidebar.py로 실행된 사이드바만 재시작합니다.
편집기 테마(editor.vim)는 새로 생성하는 편집기에 적용됩니다. 기존 편집기의 내용은 유지합니다.

디자인 참고: [Cursor 테마](https://docs.cursor.com/en/configuration/themes).
터미널 설정: [프로필 외관](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/profile-appearance),
[독립 프로필 추가 방식](https://learn.microsoft.com/en-us/windows/terminal/json-fragment-extensions).
한글 글꼴 참고: [D2Coding](https://naver.github.io/d2-coding-font/).

## 프로젝트 등록 · 파일 · Git 탭

- **Projects**: n 또는 +로 새 폴더 생성, i로 기존 폴더 등록.
- 등록 폼의 **Use existing folder**를 켜면 폴더 내용과 기존 Git 설정을 그대로 둡니다.
- 한글 이름만 사용하는 프로젝트는 ID에 영문/숫자 식별자(예: ebook)를 입력하세요.
- **Files**: 현재 열린 프로젝트의 파일 트리. 파일 선택 시 읽기 전용 팝업,
  Esc 또는 Ctrl+Q로 닫기. r로 파일 목록 다시 읽기.
- .git, .venv, venv, node_modules, __pycache__, Library, Temp, obj 및 심볼릭 링크는 트리에서 제외합니다.
- 바이너리는 미리보기를 생략하며, 텍스트는 최대 256 KiB까지 읽습니다.
- **Git**: 브랜치, staged/modified/untracked/conflict 수와 변경 경로를 표시합니다.
  탭을 보는 동안 8초마다 갱신하고 r로 수동 갱신할 수 있습니다.
- Git 상태는 인덱스를 갱신하지 않고 읽으며, 실패하거나 오래 걸리면 안내 문구를 표시합니다.
- 등록 후 세션 시작이 실패해도 등록 자체는 유지됩니다. 중복 등록 대신 프로젝트를 다시 열어주세요.

검증 명령:

```bash
.venv/bin/python -u -m unittest discover -s . -p test_workspace.py -v
```

이 PC의 Codex 샌드박스는 Python 스레드 종료에 제한이 있어, UI 검증은 일반 실행 환경에서 수행했습니다.

## 창 크기 · 에이전트 선택 · 통합 터미널

- 사이드바와 편집기 사이 세로 경계선을 드래그하면 사이드바 너비가 바뀝니다.
- Claude/Codex 사이 경계선은 좌우, 편집기/AI 및 터미널 경계선은 위아래로 드래그하세요.
- tmux 3.6에서 위쪽 창 제목이 가로 경계 드래그를 막는 현상을 확인하여 제목을 아래쪽으로 옮겼습니다.
- **a** 또는 Projects 옆 **⋯** → Claude/Codex 체크 → **Apply**.
- Codex를 끄면 Claude만 오른쪽 전체 너비를 사용합니다. 둘 다 끌 수도 있습니다.
- 기존 창을 끄는 것은 종료가 아닙니다. `saved-*` 창으로 옮겨 실행 프로세스와 스크롤을 유지합니다.
  다시 켜면 같은 창을 복원합니다. 새 프로젝트는 체크된 AI의 창만 생성합니다.
- **Ctrl+백틱(`)**: 하단 터미널 열기/숨기기. 마지막 사용한 터미널을 복원합니다.
- **Ctrl+Shift+백틱**: 새 Bash 터미널 생성.
- 모든 터미널에서 쓸 수 있는 대체 키는 **Ctrl+b → t**입니다.
- 사이드바 **Terminal** 탭에서 Ubuntu · Bash / PowerShell / Windows CMD를 선택하고 **+ New**를 누르세요.
- 터미널 목록을 선택하면 해당 셸을 하단에 복원합니다. **Show/Hide**도 실행 중인 셸을 유지합니다.
- Windows 셸도 프로젝트 폴더에서 시작합니다. CMD는 WSL UNC 경로를 pushd로 임시 드라이브에 연결합니다.
- CMD에서 명령 해석과 충돌하는 특수문자가 있는 경로는 Bash/PowerShell을 사용하세요.
- Windows Terminal에는 구분되는 CSI-u 시퀀스를 보내는 단축키 2개를 등록했습니다.
  Ctrl+Space는 터미널 전환에 사용하지 않습니다. 다른 터미널에서는 Ctrl+b → t를 사용하세요.
- Windows Terminal 설정 원본 백업은 `data/backups/windows-terminal-*.json`에 있습니다.

기능 참고: [VS Code 터미널](https://code.visualstudio.com/docs/terminal/basics/),
[터미널 프로필](https://code.visualstudio.com/docs/terminal/profiles),
[Windows Terminal 키 매핑](https://learn.microsoft.com/en-us/windows/terminal/customize-settings/actions).
경계 문제 참고: [tmux 논의 #4823](https://github.com/orgs/tmux/discussions/4823).

실제 마우스 입력과 셸을 포함한 검증은 운영 서버와 분리된 테스트 서버에서 수행했습니다.
`check-layout.py`는 `TMW_SOCKET=tmux-ui-test`에서만 실행할 수 있으며 테스트 종료 후 해당 서버를 정리해야 합니다.

## 터미널 우측 툴바

터미널 바로 위 한 줄 툴바 우측에 작은 버튼이 표시됩니다.

- **+**: 현재 선택된 셸로 새 터미널 생성.
- **▾**: Bash / PowerShell / CMD를 선택하여 새 터미널 생성.
- **×**: 터미널과 툴바를 숨기고 셸 프로세스는 보존.

버튼은 창 크기 조절 경계와 분리되어 있습니다. 경계 드래그는 그대로 동작합니다.
사이드바 Terminal 탭에도 작은 + / 표시 전환 / × 버튼이 있습니다.

Windows Terminal의 현재 지원 구현에는 OSC 22 포인터 모양 전환이 없습니다.
따라서 tmux 경계선 위에서 OS 마우스 포인터를 ↔/↕로 바꾸는 요청은 이 구성에서 미구현입니다.
근거: [Windows Terminal OSC 처리 구현](https://github.com/microsoft/terminal/blob/main/src/terminal/parser/OutputStateMachineEngine.cpp).

현재 창에서 직접 **+ → ▾에서 CMD 선택 → ×** 순서로 눌러 버튼의 위치와 실제 동작을 확인해 주세요.

## AI 상태 자동 감지

사이드바가 실행되는 동안 **8초마다** 전용 tmux 서버의 등록된 AI 창을 읽습니다.
여러 프로젝트가 열려 있어도 socket별 파일 lock과 캐시로 수집을 공유합니다.
상태바 갱신이나 spinner 갱신마다 capture-pane을 호출하지 않습니다.

- **Not started**: 해당 창에서 AI CLI를 실행하지 않은 상태.
- **Working**: 현재 화면의 esc to interrupt / esc to cancel 표시.
- **Waiting**: 현재 선택 메뉴 또는 확인 요청.
- **Draft**: 입력창에 사용자가 입력한 글자가 남아 있음.
- **Idle**: 입력창이 비어 있음. ANSI dim 자동 추천은 입력으로 세지 않음.
- **Unknown**: 지원하지 않는 화면, 수집 실패, 24초 이상 갱신되지 않은 결과.

출력이 잠잠하다는 이유만으로 작업 완료를 추정하지 않습니다.
Done은 명시적인 외부 이벤트로만 표시하며, 최근 수동 이벤트는 새 화면 상태가 나타나기 전까지 우선합니다.
수동 이벤트는 최대 60초 동안 우선하고, 자동 감지 Waiting을 읽음 처리한 상태도 다음 상태 변경까지 유지합니다.

읽는 내용 자체는 저장하지 않습니다. 상태·원인 코드·pane ID·시간만
`data/state/observed-tmux-ui-preview.json`에 원자적으로 저장합니다.
서버당 수집 예산은 0.8초이며, 개별 캡처에는 최대 0.15초 제한을 둡니다.

수동 갱신:

```bash
../bin/update-status --force
```

AI CLI 화면은 버전에 따라 달라집니다. 현재 실제 미리보기 창은 CLI 실행 전이므로,
사용 중인 Claude/Codex를 실행한 뒤 Working → Waiting/Idle 전환을 직접 확인해 주세요.
기존 운영 서버와 별도 서버의 세션은 읽지 않습니다.

프로젝트 탭과 대화창
-------------------
- 프로젝트를 클릭하면 현재 그룹에 탭이 열립니다. 분할된 그룹마다 독립된 탭 줄과 해당 프로젝트의 대화창을 표시합니다. 최대 두 그룹을 좌우 또는 위아래로 배치합니다.
- 탭을 탭 줄로 드래그하면 순서 변경 또는 그룹 간 이동이 됩니다. 본문 가장자리로 드래그하면 분할 위치를 미리 표시합니다. 그룹 오른쪽 `◫` / `⊟` 버튼은 현재 프로젝트를 좌우 / 상하로 나눠 엽니다.
- Claude만 연결된 프로젝트는 대화창 하나, Claude와 Codex가 연결된 프로젝트는 두 대화창을 표시합니다. 각 대화창은 자기 프로젝트의 기록과 입력창을 갖습니다.
- 대화창 오른쪽 `×`로 해당 창을 숨기고 그룹의 `◉`로 다시 표시합니다. 탭의 `×`는 탭을 닫습니다. 이동·닫기·재열기 시 작성 중인 입력을 보존합니다.
- 탭을 선택하면 최신 메시지가 있는 맨 아래로 이동합니다. 위로 스크롤해서 이전 기록을 읽을 수도 있습니다. Ctrl+PageUp / Ctrl+PageDown으로 탭을 전환합니다.
- 그룹과 두 AI 사이 경계를 드래그해 비율을 조절합니다. 별도 터미널은 Ctrl+` 및 사이드바 Terminal에서 엽니다.
- 왼쪽 Projects에 `⋯`와 `+`를 모았습니다. 사이드바 하단 `▤ 상단` / `▥ 왼쪽` 버튼으로 배치를 변경합니다. 분할 대상 드롭다운과 사이드바 분할 버튼은 제거했으며, 탭 드래그 또는 그룹의 분할 버튼을 사용합니다. 목록 스크롤 및 외곽 경계의 크기 조절을 지원합니다.
- 기존 편집기·AI 프로세스와 입력은 숨긴 tmux 창에 보관합니다. 이 전환에서 기존 프로세스를 종료하지 않습니다.
- 디자인 참고: [VS Code Custom Layout](https://code.visualstudio.com/docs/configure/custom-layout), [User Interface](https://code.visualstudio.com/docs/editing/getting-started/userinterface).

기존 tmux 대화와 UI 입력 연결
----------------------------
- 운영 프로젝트에서 보내면 선택한 **기존 tmux 세션의 Claude/Codex 창**에 입력합니다. UI는 그 창의 출력을 표시하므로 같은 대화를 이어 갑니다. 이전 버전의 별도 대화 기록은 파일에 보존하지만 운영 대화 화면에 섞어 표시하거나 자동 재전송하지 않습니다.
- Enter로 전송, Shift+Enter로 줄바꿈합니다. 원본 입력창에 작성 중인 내용이 있거나 AI가 작업·승인 대기 중이면 새 메시지를 보내지 않습니다. 연결 대상의 세션·pane·PID·AI 종류를 전송 직전에 다시 확인합니다.
- 같은 AI 창이 여러 개면 대화창 위의 선택 메뉴에서 대상을 명시합니다. 다른 창으로 자동 전송하지 않습니다. 메시지는 셸 명령으로 실행하지 않고 이름이 있는 tmux 버퍼로 붙여넣습니다.
- `/model` 등 해당 AI가 지원하는 슬래시 명령을 그대로 입력하고 Enter로 실행합니다. 선택 메뉴가 열리면 입력창에서 방향키 / Enter / Esc를 사용하거나 나타나는 이동·선택·취소 버튼을 누릅니다. 메뉴가 닫히면 키는 다시 일반 입력창 편집에 사용됩니다.
- 화면은 보이는 대화창만 0.5초마다 갱신하며 전송 직후 대상 세션과 AI를 알림으로 표시합니다.
- 원본 입력창의 흐린 추천 문구를 UI placeholder로 표시합니다. 빈 입력창에서 Tab을 누르면 문구가 입력되며 Enter를 누르기 전에는 전송하지 않습니다.
- Claude 입력창에서 Shift+Tab 또는 헤더의 ⇧Tab을 누르면 기존 Claude의 모드가 전환됩니다. Auto/Plan 등 실제 세션이 제공하는 순서를 그대로 사용하며 현재 모드를 표시합니다. [Claude 공식 모드 전환](https://code.claude.com/docs/en/permission-modes).
- ■ 또는 입력창의 Ctrl+C는 현재 작업 중인 선택 AI에 Escape를 전달합니다. 프로젝트를 열거나 상태를 갱신하는 것만으로 입력·모드 변경·중지가 일어나지는 않습니다.
- AI 답변 뒤 후속 입력이 없으면 프로젝트/AI 옆에 빨간 `결과`, 승인·선택 대기면 `결과 · 승인 대기`를 표시합니다. 탭을 읽기만 해서는 지우지 않고, 다음 입력/작업 재개를 기준으로 갱신합니다. 이는 터미널 상태에 따른 알림이며 관제의 별도 메시지 수신 기록을 조회하는 기능은 아닙니다.
- MyProject는 내부 워크스페이스 호스트로만 유지하며 탐색 목록에서는 숨깁니다.
- 운영 tmux에 연결되지 않은 일반 프로젝트만 자체 CLI 대화를 사용합니다. 작성 중 입력은 `data/state/desk-drafts/`에 저장합니다.

검증:

```bash
./.venv/bin/python -m unittest discover -v
TMW_SOCKET=tmux-ui-test ./.venv/bin/python check-desktop.py
./.venv/bin/python check-session-input.py
```

프로젝트별 AI 표시
-----------------
- LIVE 프로젝트 이름과 하위 항목에 실제 실행 중인 Claude/Codex를 표시합니다. 같은 프로젝트에서 둘 다 실행하면 둘 다 표시합니다.
- 프로세스가 없으면 `AI 없음`, 조회에 실패하면 `확인 불가`를 표시합니다. 약 8초마다 갱신하며 원본 세션에는 입력을 보내지 않습니다.
- 미리보기 AI 입력창의 `채팅 준비`는 실행 중인 운영 AI와 구분합니다. CLI 실행 여부를 나타내며 계정 인증 상태까지 판정하는 표시는 아닙니다.

## 승인 메뉴 · 복사 · AI 종료

- 승인 메뉴가 열린 AI의 내용창을 클릭하면 방향키로 이동하고 Enter로 선택, Esc로 취소합니다. 프로젝트 탭을 선택한 직후에도 첫 AI 내용창에서 조작할 수 있습니다.
- 내용창의 텍스트를 마우스로 드래그하면 선택한 부분이 복사됩니다. 선택 상태에서 Ctrl+C도 복사합니다. WSL에서는 clip.exe에 UTF-16으로 전달하여 한글을 보존합니다.
- 선택한 글이 없는 Ctrl+C 또는 ■는 해당 AI의 응답을 중지합니다.
- AI 제목 오른쪽 ⏻는 확인 후 선택한 원본 AI에 /exit를 전송합니다. 빈 입력창의 준비 상태에서만 종료되며, tmux pane/session은 유지합니다. ×는 화면만 숨깁니다.

복사는 UI의 OSC52 요청을 tmux가 터미널로 전달하는 경로를 사용합니다. `preview.conf`의 `set -s set-clipboard on`이 필요합니다(`external`은 앱의 복사 요청을 차단합니다). WSL의 `clip.exe`는 추가 전달 경로입니다. `check-clipboard.py`로 실제 tmux→클라이언트 PTY 전달을 검사할 수 있습니다.

## 관제에서 만든 프로젝트 자동 표시

관제가 기존 원본 tmux 서버에 프로젝트 세션을 만들면 사이드바가 주기적으로 새 세션을 등록합니다. Claude/Codex는 각 pane의 실제 실행 상태로 표시하며 프로젝트를 클릭하면 기존 AI 화면에 연결됩니다. 폴더 신뢰 확인을 자동 승인하거나 AI를 중복 실행하지 않습니다.

즉시 발견하려면 `.venv/bin/python ui-maintenance.py discover`를 실행하세요. 관제의 소스 수정·검증·적용 절차는 [CONTROL_UI.md](../CONTROL_UI.md)에 있습니다.
