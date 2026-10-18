# 작업 기록

## 2026-10-18: Workspace v3 미리보기

- 원본: /mnt/v/2.sub_project/tmux-ui/tmux-workspace-v3 (원본 변경 없음).
- 로컬 workspace/에 복사. Python 3.14.4 + Textual 7.5.0 설치.
- 기본 Python venv의 ensurepip 부재: 생성된 .venv에 uv pip로 의존성 설치.
- 전용 소켓 tmux-ui-preview 및 preview.conf 사용. ~/.tmux.conf 및 운영 설정 변경 없음.
- send-keys 제거: new-session/split-window에서 프로그램 직접 시작.
- 운영 설정의 base-index 1과 호환되도록 pane ID로 구성, 사이드바 전체 높이 적용.
- set-option의 =세션 대상 표기 오류 수정. 불완전 세션 재사용 방지 옵션 추가.
- AI 선택에 pane title 대신 @tmw_agent 사용. 이벤트 없는 상태는 unknown.
- 구성 실패 시 세션 삭제하지 않고 보존.
- 데모 Git 저장소: workspace/data/MyProject. registry/status도 workspace/data에 저장.

검증:
- Python AST 및 bash -n 통과.
- 임시 경로에서 프로젝트 등록, Git 초기화, waiting/seen 저장 검증 통과.
- Textual headless 테스트에서 트리 및 신규 프로젝트 폼 표시 통과.
- 별도 tmux-ui-test 서버에서 실제 4 pane 실행 확인: Python sidebar, vim, bash 2개.
- 160x48 기준 사이드바 폭 34, 오른쪽 편집기 및 하단 AI 2개 배치 확인.
- AI CLI 인증/자동 상태 감지 및 실제 마우스 조작은 검증 범위 밖.

기존 목표의 전체 세션 상태바/세션별 색/Windows 복사 기능은 후속 작업이며,
이번에는 사용자가 제공한 Workspace 시제품의 격리 실행을 우선 완료.


## Graphite 스타일

- Cursor 다크 UI 참고, 자체 neutral graphite + sage 팔레트 적용.
- 기본 Textual 헤더/푸터를 작은 워드마크, 프로젝트 제목, 개수, 하단 요약으로 교체.
- 컬러 이모지 폴더 제거, 명확한 상태 텍스트와 읽지 않음 표시 적용.
- 트리 선택/호버/가이드, 신규 폼, 입력창, 버튼의 배경과 강조색 통일.
- 신규 편집기용 editor.vim 추가. 기존 편집기는 재시작하지 않음.
- Windows 설치된 Cascadia Mono 확인. 12pt / cellHeight 1.15 독립 프로필 추가.
- Windows Terminal fragments/tmux-ui/workspace.json 설치; 기존 settings.json 수정 없음.
- Textual 34x47 및 34x23: 신규 버튼, Escape 폼 닫기, 상태 텍스트 검사 통과.
- vim -Nu editor.vim -i NONE -n -es 실행 통과.
- tmux-ui-test 실제 4 pane, 스타일 옵션 및 사이드바 새로고침 확인 후 테스트 서버 종료.
- tmux-ui-preview에 스타일 적용 및 sidebar 한 개만 재시작 완료.
- Windows Terminal GUI의 실제 글꼴 렌더링은 사용자가 새 전용 프로필을 열어 확인 필요.


## Projects / Files / Git

- 기존 폴더 등록 체크박스, i 단축키, 한글 프로젝트용 ID 입력 추가.
- 등록 성공 후 세션 생성에 실패해도 등록부가 유지됨을 별도 안내.
- 파일 트리 추가, 생성물/의존성 폴더와 symlink 제외. bin 스크립트 폴더는 표시.
- 파일 선택 시 전용 서버의 read-only popup. 256 KiB 제한, 바이너리 및 프로젝트 밖 경로 거절.
- Git 브랜치/스테이지/수정/미추적/충돌 및 경로 요약. 탭 활성 시에만 8초 폴링.
- Git 작업은 background thread, 명령당 1초 timeout, GIT_OPTIONAL_LOCKS=0.
- UI import, 소형/대형 탭 화면, UTF-8 파일/rename, 원본 및 Git index 보존,
  파일 읽기 경계/바이너리/크기 제한, read-only viewer를 5개 unittest로 검증 완료.
- sandbox 내 asyncio.to_thread 최소 예제도 종료 지연; 일반 실행에서는 정상.
- 일반 환경 unittest: 5 tests / 2.826s / OK.


## 마우스 크기 조절, AI 선택, 통합 터미널

- root MouseDrag1Border 바인딩 명시. tmux 3.6 pane-border-status top의 가로 드래그 실패를 실제 재현.
- border-status bottom으로 전환 후 sidebar 폭, editor/AI 높이, Claude/Codex 폭 드래그 통과.
- 신규 프로젝트 Use Claude/Use Codex 체크박스, 기존 프로젝트 a/⋯ 설정 추가.
- 비활성 AI pane은 break-pane으로 saved 창에 보관, 활성화 시 join-pane으로 복원. 프로세스 종료 없음.
- 하단 terminal drawer, Bash/PowerShell/CMD 선택, 여러 터미널 보관 및 복원 추가.
- Windows CMD는 UNC cwd로 시작할 수 없어 Windows cwd로 시작한 뒤 pushd로 프로젝트 경로 매핑.
- Ctrl+grave CSI-u 및 legacy NUL, Ctrl+Shift+grave 새 터미널, prefix t fallback을 테스트 pty에서 검증.
- 키 바인딩은 socket basename을 전달하므로 테스트 키가 preview 서버를 조작하지 않음.
- 프로젝트별 파일 lock으로 레이아웃 조작 직렬화. 레이아웃 변경 시 sidebar 폭과 AI 너비 비율 유지.
- sidebar 타이머 종료 처리 및 summary widget 참조를 보관해 unmount 시 조회 실패 방지.
- Windows Terminal settings.json의 기존 설정을 보존하고 단축키 2개 추가.
- 원본 백업: workspace/data/backups/windows-terminal-540809f77548.json.
- 5개 unittest 회귀 테스트 통과. 별도 서버의 신규 Claude-only, 모든 AI 조합, Codex PID 보존,
  터미널 PID 보존, 실제 CMD/PowerShell prompt, 3종 키 입력 및 terminal 높이 드래그 통과.


## 우측 + / 셸 선택 / × 툴바

- 사용자 요구: VS Code처럼 우측에 작은 새 터미널/닫기 버튼.
- terminal-toolbar.py 한 줄 Textual toolbar를 하단 shell 바로 위에 배치.
- +는 현재 선택된 shell, ▾는 Bash/PowerShell/CMD 메뉴, ×는 shell과 toolbar를 보관.
- 숨기기는 종료하지 않으며 PID 유지. 중복 hide도 새 terminal을 만들지 않음.
- tmux select-layout이 serialized pane ID 대신 pane-list 순서로 배치하는 문제 수정:
  각 역할의 목표 좌표를 기록하고 select-layout 뒤 필요한 swap-pane만 수행.
- 실제 shell이 두 AI pane 아래 전체 너비를 차지하는지 추가 검증.
- serialized 작업 완료 flag로 통합 검증이 배치 도중 상태를 클릭하지 않도록 보완.
- Windows 셸 사용 뒤 NUL 키 해석이 일정하지 않아 Ctrl+Space alias 제거.
  등록한 CSI-u Ctrl+grave / Ctrl+Shift+grave 및 prefix t 유지.
- native border 위 mouse_x/mouse_y가 비어 나오는 tmux 3.6 제약 때문에 toolbar를 별도 pane으로 구현.
- 실제 pty 마우스 클릭으로 × 보관/PID 보존, + 생성, ▾ CMD 메뉴 생성 통과.
- 일반 unit/UI 테스트 6개 통과. 기존 마우스 resize/단축키/Windows shell 실행 통합 검증 통과.
- 현재 Windows Terminal OSC dispatch에 mouse pointer shape OSC 22 없음 확인.
  OS resize pointer 전환은 미완료라고 사용자에게 명시. 별도 host 지원 필요.


## AI 상태 자동 감지

- watcher.py 추가: preview socket만 읽으며 list-panes/capture-pane 외 tmux 조작 없음.
- sidebar의 8초 background 수집, socket별 flock + 캐시로 다중 수집 억제.
- 수집 예산 0.8초, metadata 0.2초/capture 0.15초 timeout, snapshot atomic replace.
- 실제 실행 프로세스 이름/자식 cmdline으로 CLI 실행 여부 확인; shell의 과거 출력은 무시.
- ANSI dim 추천/SGR22 및 RGB 내 0 구분, 빈 prompt와 실제 draft 구분.
- busy hint, cursor 근처 선택 목록/확인 요청; 모호하면 unknown. 무출력 완료 추정 없음.
- 최근 수동 이벤트/자동 상태 병합, 읽음 timestamp 및 stale 24초 처리.
- bin/update-status 명시적 수동 갱신 entry point 추가.
- 14개 unit/UI 테스트 통과 (4.454s).
- tmux-ui-test에서 가짜 codex 프로세스로 실제 ANSI capture idle/busy/waiting/draft/idle 통과.
- 실제 수집 0.0048s, 키 전송/실제 AI 실행 없이 검증, 테스트 서버 정리 완료.
- 현재 preview AI pane 둘 다 bash: 실제 CLI UI 화면 전환은 사용자가 실행 후 확인 필요.

2026-10-18 프로젝트 탭 / 작업 영역 배치
- Demo Web(HTML/CSS/JS)와 Demo Python(dataclass 작업 목록) 예제 추가, data/ 편집용 복사본 등록. AI 자동 실행 없이 시험.
- 드래그 가능한 프로젝트 탭: 클릭으로 세션 전환, 상하/좌우 드래그 순서 저장, 많은 항목의 스크롤.
- 드롭다운 대상으로 좌우/상하 코드 분할(최대 3개). 숨길 때 편집기 보존, 같은 프로젝트 다시 열 때 기존 프로세스 복원. 원본 프로젝트의 미저장 버퍼와는 독립.
- 동일 탐색 영역을 왼쪽/상단으로 도킹. 상단 전체 폭/마우스 높이 조절, 왼쪽 폭 조절, 배치별 스크롤. 작은 화면 도킹 실패는 이전 배치로 복원.
- 별도 tmux-ui-test에서 실제 PTY 마우스 드래그·단축키·터미널 +/×·프로필과 프로젝트 전환/양방향 분할/높이 조절 통과. 기존 편집기·AI·터미널 PID 보존 확인.

2026-10-18 편집 영역 탭 / 상단 기능 유지 수정
- 프로젝트 클릭은 현재 워크스페이스에 편집 탭을 여는 동작으로 변경. 프로젝트 클릭 시 세션이 전환되어 상단 패널이 왼쪽으로 바뀌던 문제 제거.
- 편집 영역 전용 탭 줄 추가. 열린 탭 재정렬, 선택, 닫기/재열기, ↔ 옆 / ↕ 아래 대상으로 드래그 분할. 편집기는 숨길 때 보존하며 PID 재사용 확인.
- 상단에서 트리를 숨기던 CSS 제거. Claude/Codex 상태와 에이전트 설정을 왼쪽과 동일하게 유지. 도구 버튼 3행 높이와 이름 표시.
- UI 자동 검사 17개 통과. check-editor-tabs.py 시험 서버에서 탭 전환/정렬/재열기/두 방향 분할/상단 배치 유지 및 실제 탭 줄 렌더링 확인. 기존 check-layout.py도 모든 터미널/단축키/마우스/프로세스 보존 검사 통과.

2026-10-18 사용자 부재 중 마무리 점검
- 실제 PTY의 SGR 마우스로 편집 탭을 ↔/↕ 버튼에 드래그하여 좌우/상하 분할하고 탭 순서를 바꾸는 종단 검사 추가·통과.
- 선택한 편집 그룹에 탭 강조 동기화 및 선택 탭 자동 스크롤. 좁은 창에서는 도구 버튼 폭을 줄이고 넓히면 이름 복원.
- CLI/새 프로젝트 폼에서 최초 실행 시 편집 탭 초기화. 너무 작은 창은 기존 배치로 복원한 뒤 창 확대 시 숨긴 탭 줄을 재사용.
- 여러 세션이 존재할 때 break-pane 기본 대상이 현재 세션으로 잡히는 문제 발견. 원래 pane의 session_name을 조회하여 break-pane -t session:으로 지정. 편집기·터미널이 다른 워크스페이스로 옮겨가지 않도록 수정.
- 최종 검증: 자동 검사 18개, check-layout.py 전체 통과. check-editor-tabs.py 실제 마우스/신규 CLI/작은 창 복원 통과. 미리보기 탐색 UI만 갱신하고 기존 편집기·AI·터미널 PID 보존을 적용 전후 확인.

2026-10-18 기존 운영 세션 LIVE 연결
- 운영 tmux의 12개 세션을 읽기 전용 LIVE 프로젝트로 등록. control/unity를 MyProject의 편집 탭으로 열고 control 선택.
- live_tmux.py는 list-sessions/list-panes/capture-pane만 허용. live-view.py에서 현재 화면만 1.5초 간격으로 조회하며 창/패널 선택 제공. 원본에 attach/send-keys/resize/이동 없음, 화면 내용 파일 저장 없음.
- 자동 검사 21개 통과. 별도 시험 서버에서 기존 소스 세션을 LIVE 탭으로 열고 렌더링/원본 프로세스 보존 확인. 실제 control/unity LIVE 뷰 렌더링 확인. 운영 pane 18개의 PID와 크기가 연결 전후 동일함을 확인.

2026-10-18 채팅 입력 UI와 둥근 탭
- 하단 Claude/Codex를 대화 기록 + TextArea 입력 + 보내기/중지 형태로 구성. Enter 전송, Shift+Enter 줄바꿈. CLI stdout JSON 이벤트를 대화로 표시하고 자체 대화 ID로만 재개.
- CLI 요청은 사용자 전송 시에만 시작. 테스트는 가짜 CLI로 stdin 리터럴 전달/응답/재개/중지 검증, 실제 AI에 테스트 요청하지 않음. 로그인/계정 연결 실응답은 사용자 확인 대상.
- 기존 preview 에이전트 프로세스는 원래 세션 내 숨겨 보관하고 새 채팅 UI 추가. 운영 LIVE는 읽기 전용 유지.
- 편집 탭과 상단 워크스페이스 탭에 둥근 모서리/좌우 테두리/간격 추가. 실제 tmux의 둥근 문자 렌더링과 마우스 드래그/양방향 분할 검증.
- 상태 수집기는 chat UI의 busy 메타데이터를 사용하며 기존 네이티브 CLI 화면 감지도 유지.
- 최종 적용 확인: 자동 검사 24개 통과. 별도 tmux의 채팅 UI 전환/기존 프로세스 보존과 둥근 탭/드래그/분할 통과. 실제 미리보기 Claude·Codex 입력창 및 둥근 탭 렌더링 확인, 기존 에이전트 PID 2개 모두 보존.

2026-10-18 데모 제거 / 프로젝트별 실행 AI 표시
- Demo Web·Demo Python을 프로젝트 레지스트리와 열린 편집 탭에서 제거. 기존 파일/미저장 버퍼와 프로세스는 보존, 독립 데모 세션은 archived-demo-*로 이름을 바꿔 활성 워크스페이스에서 제외.
- source_agents를 별도 메타데이터로 추가하여 LIVE 프로젝트의 실제 Claude/Codex 프로세스와 자식 프로세스를 확인. 로컬 채팅 사용 설정과 운영 CLI 실행 여부를 구분.
- 사이드바 이름·하위 항목에 Claude/Codex/AI 없음/확인 불가 표시, 공유 잠금으로 8초마다 한 번 갱신. 실제 조회 0.014초.
- 자동 검사 26개 및 별도 tmux 통합 검사 통과. 실제 레지스트리와 MyProject 열린 탭에서 데모 부재 확인, UI 갱신 완료.

2026-10-18 그룹별 탭과 프로젝트 대화창 재구성
- VS Code 공식 레이아웃 자료를 참고해 그룹마다 독립 탭 줄, 둥근 탭 경계, 탭 드래그 위치 표시를 구현. 최대 두 그룹의 좌우/상하 분할 및 비율 조절.
- 프로젝트별 Claude/Codex 실행 상태에 맞춰 하나/둘 대화창 표시. 기록·입력·닫기/복원은 해당 프로젝트에 소속. 전역 하단 AI 영역 제거.
- 탭 선택 시 최신 메시지로 이동. 이동/닫기/재열기에서도 위젯과 작성 중 입력 보존. 두 뷰의 동일 대화 동시 요청은 잠금으로 방지.
- 왼쪽 중복 프로젝트 영역 제거, Projects 내부에 추가/설정 배치. LIVE 문구 없는 좁은 탭, 작은 전송/중지 아이콘.
- 자동 검사 31개 통과. 격리 tmux 서버에서 원래 PID 보존, 실제 마우스 탭 그룹 이동, 개별 Codex 닫기, 독립 탭 줄과 1/2개 입력창, 터미널 표시/숨김 통합 검사 통과. 실제 AI 요청 없이 검증.
- 운영 화면은 읽기 전용이며 전송은 별도 CLI 대화임을 UI와 문서에 명시. 기존 미리보기 프로세스/입력은 보관 창에 그대로 유지.
- 실제 MyProject 미리보기에 적용 완료. 기존 pane 32개 중 사이드바만 UI 갱신, 나머지 31개 PID 유지. 현재 보이는 native pane은 sidebar/editor 둘이며 design/control 독립 그룹 확인. 운영 서버 pane PID·가로·세로 전체가 적용 전후 동일.

2026-10-18 여백과 상태 아이콘 다듬기
- 입력창 높이 5→4행, 입력 영역 3→2행. 바깥 여백/하단 안내 여백 제거, 대화 간격 축소. 탭 사이 공백 제거, 선택 탭에 차분한 파란 테두리 적용.
- Claude 살구색/Codex 하늘색. 운영 상태도 캐시로 읽어 작업 중 점자 회전, 입력 대기 노랑, 준비 초록 표시. 프로세스만 확인되고 작업 상태를 모르면 실행 중으로 구분. 8초 수집, 애니메이션은 캐시로만 갱신.
- 읽기 전용 상태 수집 0.039초 확인. 자동 검사 32개 통과. 실제 사이드바에서 애니메이션 프레임 변화와 작업 중/입력 대기/준비 표시 확인. CSS 자동 반영, 사이드바만 갱신.

2026-10-18 사이드바 탐색 공간 정리
- 옆/아래/닫기 도구 줄과 분할 프로젝트 드롭다운 삭제. 상단/왼쪽 배치는 하단 한 줄의 ▤ 상단 / ▥ 왼쪽 버튼으로 이동하고 현재 배치를 색으로 표시.
- 사이드바 UI 및 탭 회귀 검사 11개 통과. 그룹 탭의 분할/닫기 기능은 계속 사용.

2026-10-18 기존 세션 입력 연결 / 추천 / 모드 / 결과 알림
- 사용자 후속 지시: UI에서 선택한 세션으로 보낸 메시지는 그 기존 tmux 세션에도 보여야 함. 기존 send-keys 금지 원칙의 예외는 사용자가 선택한 AI에 직접 전송·중지·모드 전환하는 동작으로 한정. 백그라운드 키 입력과 무관한 세션 조작은 계속 금지.
- session_input.py에서 세션/pane/PID/실행 AI/입력 상태 검증 후 고유 버퍼로 한글·여러 줄 그대로 paste-buffer -p -r, Enter. 연결이 바뀌거나 기존 입력이 있으면 중단. 운영 프로젝트는 별도 Conversation.send 사용 안 함.
- source 출력과 ANSI 흐린 추천 문구를 UI에서 표시. Tab은 빈 입력창에 추천만 삽입, Enter 전송. Shift+Tab/BTab 및 작은 모드 버튼으로 기존 Claude 모드 전환, 실제 footer 모드 표시.
- MyProject 탐색 숨김. 완료 결과/승인 대기를 빨간 결과로 프로젝트·AI 둘 다 표시. 캐시에 상태와 본문 해시만 저장하고 읽기/탭 열기는 확인 처리하지 않음. 다음 작업/사용자 전송으로 갱신. 관제 메시지 전달 자체를 검증하는 기능은 아님.
- 자동 검사 39개 통과. 격리 fake CLI의 실제 tmux에서 한글/줄바꿈/리터럴 전송, 다른 세션 무변경, 동일 창 응답, 추천 추출, Shift+Tab Auto→Plan 검증. 운영 video에는 테스트 메시지를 보내지 않았음.
- UI 갱신은 자신의 별도 CLI 요청 잠금을 확인한 뒤 저장된 입력/탭으로 복원. 운영 세션은 유지하고 미리보기 Desktop/Sidebar 프로세스만 재시작. 실제 결과 표시와 MyProject 제거, 추천/모드 안내 렌더링 확인.
- 중앙만 글꼴 크기 변경은 터미널 셀 모델에서 지원되지 않아 전체 터미널 확대 적용 여부 질문 대기.

2026-10-18 슬래시 명령과 관제 전달 확인
- control의 원본 Claude %4에서 사용자 메시지 관제니와 응답 확인. UI도 동일 socket/session/pane으로 연결됨. 재전송하지 않음.
- /model 등 기존 AI 명령을 전송하고, 메뉴 감지 후 방향키/Enter/Escape 및 전용 한 줄 버튼으로 조작. 매 키마다 대상 AI와 메뉴 상태 재확인, 닫힌 메뉴에는 키를 보내지 않음. 로컬 초안은 보존.
- 가시 UI 화면 갱신 2초→0.5초. 전송 성공 시 대상 세션/AI 알림.
- 입력/UI 검사 8개, Desktop 검사 4개 통과. 격리 실제 tmux의 fake CLI에서 /model 열기→Down→Enter 선택 및 다른 세션 무변경 통과. 운영 AI 모델을 테스트로 변경하지 않음.

2026-10-18 unity Claude/Codex 화면 중복 수정
- 원본 unity는 Claude pane %2 하나지만, Claude의 자식 Codex 프로세스를 별도 AI로 세던 오류. pane의 전면 AI를 우선하여 하나만 판정. 래퍼는 후보가 하나일 때만 인정.
- 연결 수집/상태 수집/메시지 대상 판정에서 같은 소유자 규칙 사용. Claude pane을 Codex 전송 대상으로 선택할 수 없게 회귀 검사. 연결 실패 시 이전 화면도 지워 중복 잔상이 남지 않게 함.
- 자동 검사 43개와 격리 tmux 메시지/명령 메뉴 전송 검사 통과. 실제 unity 레지스트리를 Claude 1개로 갱신, Sidebar/Desktop UI 적용.

2026-10-18 흰 배경 / 결과 색 / stock 개수 / 승인 방향키
- 원본 ANSI의 default 배경·반전이 흰 박스로 렌더링되는 문제: 공통 terminal_render로 배경/반전 제거, 글자색·굵기·흐린 추천은 유지.
- 미리보기 서버에서 상속된 NO_COLOR=1 때문에 전체 UI가 흑백 필터로 표시되던 원인 확인. Sidebar/Desktop/LiveView 생성 시 UI 프로세스 내부에서 해제. 원본 운영 세션 환경은 변경하지 않음.
- stock: 원본 대화용 Claude %15 하나. transcribe/keyframes/extract/collect 작업창의 하위 프로세스는 독립 AI로 세지 않도록 판정 범위를 전면 명령과 pane 자체 argv로 제한.
- 사용자 요청으로 마케팅 승인 메뉴 %5에서 Down만 전송하여 1→2 이동 확인, Up으로 1 복원. Enter/승인은 전송하지 않았으며 승인 메뉴 유지 확인.
- 자동 검사 47개 및 격리 tmux 입력/메뉴 검사 통과. 실제 사이드바 결과 텍스트의 #f08080 ANSI 확인, stock Claude 1개 확인.

2026-10-18 좁은 분할창의 긴 입력 구분선 제거
- 원본 tmux 입력 구분선(Unicode 수평선)만 채팅 렌더링에서 제거. 브랜치명이 있는 구분선은 이름만 유지. 실제 표의 테두리/대화/흐린 추천/모드는 보존.
- 렌더링 검사 5개 통과. 선택한 사이드바 행에서도 결과 텍스트를 빨간색으로 유지하는 검사 포함.

2026-10-18 승인 키보드 포커스 / 드래그 복사 / AI 종료
- 승인 키가 Composer에만 연결되어 내용창에서 동작하지 않던 문제 수정. 내용창 클릭 및 탭 선택 후 해당 패널에서만 방향키/Enter/Esc 처리. 다른 AI 내용창에는 전달하지 않음.
- 드래그 선택 후 자동 복사, 선택한 글이 있으면 Ctrl+C는 응답 중지 대신 복사. Windows clip.exe에는 UTF-16 전달, 터미널 OSC52도 유지. 선택 중 실시간 갱신으로 선택이 깨지지 않도록 화면 갱신 보류.
- AI 제목에 ⏻ 추가. 대상 session/agent/pane 확인창, 취소 시 무전송. 준비 상태와 PID 재확인 후 /exit. 선택 pane의 remain-on-exit을 켜서 세션 보존. 작업·승인·입력 중이면 종료 거부. × 숨기기와 분리.
- 자동 검사 52개, 격리 tmux 전송/메뉴/정상 종료/세션 유지 검사, Desktop 마우스 탭 이동·닫기·갱신 통합 검사 통과. 운영 AI에는 종료나 승인 입력을 보내지 않음.
- 사용자가 https://github.com/jangbm/tmux_ui.git 연결·커밋·푸시를 명시 요청. 기존 로컬 커밋 전용 원칙에 대한 이번 작업의 사용자 승인으로 처리. 로컬 데이터·대화·초안·가상환경 제외.

2026-10-18 복사 전달 경로 수정
- 사용자가 실제 붙여넣기 실패를 보고. 실행 중 preview 서버의 set-clipboard가 external이라 Textual의 OSC52를 차단하는 것을 확인. clip.exe는 WSL interop에 의존하므로 유일한 대체 경로로 사용할 수 없음.
- preview.conf에 set -s set-clipboard on 추가. 운영 default 서버 설정은 유지. 복사 요청 시 짧은 알림 표시, 선택 내용이나 클립보드는 로그에 저장하지 않음.
- check-clipboard.py: 임시 소켓/PTY에서 external 차단 재현 → 프로젝트 설정 적용 → 한글·줄바꿈 OSC52가 tmux 클라이언트 터미널까지 전달됨과 tmux 버퍼 원문 일치 검증. 테스트는 사용자 Windows 클립보드를 덮어쓰지 않음.

2026-10-18 새 tmux 프로젝트 자동 등록 / 관제 공동 편집
- 기존 refresh_connections가 등록된 프로젝트의 상태만 갱신하여 관제가 만든 test 세션이 누락됨. 알려진 원본 socket의 list-panes 전체 결과로 새 세션을 매 주기 발견하고 등록하도록 수정. 최초 등록이 없으면 기본 tmux socket을 발견 대상으로 사용.
- session+socket으로 중복 방지. ID 충돌 시 안정적인 해시를 붙이며 로컬 프로젝트, 기존 이름·순서·숨김·pane 선택을 보존. 원본 서버에는 읽기만 수행.
- 실제 test의 Claude %24와 Codex %25 발견. Sidebar 갱신 후 두 자식 항목 표시 및 Desktop 생존 확인.
- CONTROL_UI.md와 ui-maintenance.py status/discover/reload 추가. control도 공유 UI 소스를 수정할 수 있다는 사용자 요청을 AGENTS.md에 반영. 파일 쓰기 권한과 도구별 작업 폴더 제한은 구분.
- 자동 등록 변경 후 전체 검사 55개 통과. 테스트용 Sidebar에서는 실제 호스트 발견을 mock하여 운영 프로젝트가 테스트 레지스트리에 섞이지 않게 격리. 실제 전체 연결 갱신 0.049초, test Claude 1/Codex 1 확인.

2026-10-18 삭제된 세션의 사이드바 잔상 수정
- 원본 test 세션은 없고 test2만 존재하는데 등록 정보가 남아 test가 계속 보이던 문제 수정.
- 성공한 세션 목록 조회에서 사라진 프로젝트에 source_missing 표시, 사이드바에서 제외. 일시적인 소켓 오류·시간 초과로는 숨김 상태를 변경하지 않음. 동일 세션 재생성 시 자동 복원.
- 등록 메타데이터·초안·대화·실제 폴더는 보존. 원본 세션에는 읽기만 수행.
- 소스 어댑터 검사 12개 통과. 실행 중 Sidebar 갱신 후 test 제거, 실제 존재하는 test2 유지 확인.

2026-10-18 관제 Claude 전송 차단 안내 확인
- 사용자 오류 제보 후 원본 control Claude %4 읽기 확인: idle/empty-prompt, 추천 문구는 ANSI dim이며 입력으로 오인하지 않음. 발생 당시 상태는 저장되지 않아 당시 차단 원인 단정하지 않음. 테스트 메시지/키 전송 없음.
- 전송 거부 안내를 실제 상태별(작업 중, 승인 메뉴, 원본 초안, 질문 대기, 상태 불명)로 분리. 전송 직전 상태 변경도 실제 이유 표시. 기존 초안 보존과 전송 가드는 유지.

2026-10-18 Cursor / VS Code 조사 후 작업 흐름 개선
- 사이드바 프로젝트 검색, 작업/결과/승인 필터, 선택 프로젝트 상단 고정.
- 탭 우클릭·⋯ 메뉴: 고정, 분할, 그룹 이동, 다른 탭 닫기. 프로젝트 결과 배지.
- 원본 AI 상태별 입력 안내, 작업 중 +/Enter 대기열 등록. pane/PID 고정, 승인·초안·연결 변경 시 정지, 재시작 시 일시정지, 불명확한 전송 시도 재실행 금지. 등록은 사용자 조작만 허용.
- 현재 화면 Ctrl+F 강조 검색, 최신 내용 이동, 선택 글 복사 버튼. 한 줄 자동 확장 입력창과 중립 회색 색상.
- 선택한 프로젝트의 Git diff·추적 브랜치 미푸시/수신 대기 수치 표시. 마지막 fetch 기준을 명시.
- 프로젝트 Git/고정 명령이 workspace owner 대신 실제 열린 프로젝트를 대상으로 하도록 연결.
- 전체 자동 검사 64개 통과, 마지막 종료/연결 변경 대기열 가드 후 입력 검사 14개 추가 확인. 격리 tmux Desktop/입력 통합 검사 통과.
- 실제 좁은 사이드바에서 검색창과 필터를 세로 배치하고 기본 Input 여백을 제거하여 잘림 방지. 실행 중 Desktop/Sidebar 생존과 한 줄 입력창 확인.

2026-10-18 전체 자체 점검 (사용자/관제 요청)

| 우선순위 | 발견 사항 | 조치 및 검증 |
|---|---|---|
| P1 | 입력창에서 선택한 글의 Ctrl+C가 응답 중지로 처리됨 | TextArea 선택을 복사로 우선 처리, UI 회귀 검사 |
| P1 | Yes/번호로 시작하는 흐린 추천을 승인 선택지로 오인 | ANSI dim을 판정에 반영, 실제 승인 선택지는 유지 |
| P1 | 과거 메뉴의 선택지/안내가 현재 메뉴 판정에 섞일 수 있음 | 현재 커서 근처 선택지와 화면 하단 안내로 한정 |
| P1 | 원본 AI pane 재생성 후 기존 pane에 연결이 남음 | 유일한 새 AI는 화면만 재연결, 기존 예약 전송은 정지 |
| P1 | 한글만 있는 tmux 세션명 발견 시 slug 예외 | socket/session 기반 안정적 해시 ID |
| P2 | 화면 갱신마다 같은 대상 목록을 두 번 조회 | 화면 읽기에만 바로 얻은 목록 재사용, 입력 시 재검증 유지 |
| P2 | 다중 소켓에서 연결 조회가 전체 시간 예산을 무시 | 남은 시간으로 명령 timeout 제한, 소진 시 조회 중단 |
| P2 | README의 복사 미지원·별도 입력 주입 없음 등 오래된 설명 | 현재 구현과 실제 제한 기준으로 다시 정리 |
| P2/남음 | 화면 기반 상태 판정, 현재 화면만 검색, 최대 2개 그룹, 대기열 첫 항목만 편집 | 제약 명시; 전체 세션 프로토콜/대화 기록 연동은 별도 작업 |

운영 읽기 점검: control Claude/Codex, unity Claude, ebook Claude, stock Claude, marketing Claude/Codex 모두 점검 순간 idle/empty-prompt. 흐린 추천 존재를 확인했고 입력으로 계산하지 않음. 원본 화면·대화는 공개 문서에 저장하지 않음. 최초 전체 상태 갱신 0.0332초. 운영 서버에는 키 전송·종료·설정 변경 없이 읽기만 수행.

점검 결과와 검증:
- 위 P1/P2 수정 완료. 사이드바 상태 갱신 때 고정 표시(★)가 사라지던 문제도 수정하고 회귀 검사 추가.
- 한글 다중행 붙여넣기, 입력 선택 복사, 원본 pane 교체 시 화면 재연결/대기열 정지, 28×12~160×45 크기 변화를 합성 UI로 검사. 운영 AI 입력은 mock으로 금지.
- 격리 tmux 통합 검사: 레이아웃·마우스 탭 이동·분할·터미널 조절·상태 판정·Desktop 갱신·한글 입력·승인 메뉴 방향키·OSC52 복사 모두 통과. 기존 시험 서버가 있으면 덮어쓰지 않도록 검사 스크립트를 보강하고 레이아웃 시험 서버는 종료 시 정리.
- Windows CMD/PowerShell 실제 실행은 현재 도구 환경에서 WSL interop을 사용할 수 없어 건너뜀. 메뉴 선택/라우팅 검사는 통과했으나 실제 실행 검증과 구분.
- 합성 화면 2개, 5초 headless 측정: Python CPU 0.062초(단일 코어 기준 약 1.2%), 대상 조회/화면 읽기 각 20회. 운영 서버 전체 CPU 측정값은 아님. 조회 중복 제거로 화면 갱신의 대상 조회 횟수를 절반으로 줄임.
- 공개 대상 소스 60개를 알려진 토큰/개인키 패턴으로 검사해 일치 없음. data/·가상환경·환경파일 Git 제외 확인. 운영 대화 캡처는 공개 파일에 추가하지 않음.
- 남은 수동 확인: Windows Terminal의 실제 한글 IME 조합·클립보드 붙여넣기·CMD/PowerShell 실행. 자동 검사는 한글 완성 문자열과 OSC52 전달까지 검증하며 실제 IME/OS 클립보드를 대체하지 않음.
- 남은 구조 제약: 상태는 CLI 화면 휴리스틱이므로 CLI 버전·화면 형식 변경에 취약. 검색은 현재 캡처 화면, 분할은 최대 2개 그룹. 전체 대화 기록 검색·임의 다중 그룹은 별도 확장 사항.
- 최종 전체 단위/UI 검사 66개 통과. preview Desktop와 Sidebar 갱신 완료. 운영 원본 서버는 변경하지 않음.

2026-10-18 디자인 자체 점검 및 개선

참고 기준: [VS Code Custom Layout](https://code.visualstudio.com/docs/configure/custom-layout)의 그룹별 탭·고정·좁은 탭 탐색과 [Cursor Agent](https://cursor.com/docs/agent/overview)의 대화 중심 작업 흐름. GUI의 픽셀 디자인을 복제하기보다 터미널 셀 단위에서 선택·상태·입력 위치를 명확히 하는 방향.

| 우선순위 | 발견 | 수정 / 남은 사항 |
|---|---|---|
| P1 | 창 축소 후 절대 배치 영역이 이전 크기로 남아 입력창·도구 잘림 | 실제 Stage 크기 변경 후 그룹 재배치. 화면 안에 입력창이 있는지 회귀 검사 보강 |
| P1 | 좁은 승인 메뉴에서 고정 폭 버튼이 넘침 | 6개 버튼을 가용 폭에 균등 배치. 키보드 기능 유지 |
| P2 | 선택·고정·드래그 중 탭의 차이가 약함 | 선택 탭 밝은 테두리/굵기, 고정 배경/◆, 드래그 배경. 긴 이름 툴팁과 단일행 생략 |
| P2 | 축소 후 선택 탭이 가려짐 | 그룹 크기 변경 후 선택 탭이 보이도록 스크롤. 48열 미만에서는 분할 단추를 ⋯ 메뉴로 통합 |
| P2 | 제목 도구와 상태가 좁은 AI 창에서 겹침 | 38열 미만 상태를 두 번째 행으로 배치, Claude 모드 버튼을 짧은 문구로 표시 |
| P2 | AI 구분·보조 글자 대비·회색/녹색 혼용 | Claude 따뜻한 색/Codex 푸른색 제목, 상태·힌트 밝기 개선, 탭/구분선/포커스 푸른 회색 통일 |
| P2 | 검색 0건·빈 터미널이 빈 화면 | 검색/필터 해제 안내, +로 터미널 생성 안내. Files/Git/Terminal 기본 문구 한글 통일 |
| P2 | 보조 패널 버튼·패딩 불일치 | Git 버튼 전폭·동일 테두리, Git/Terminal 패딩 축소, 사이드바 활성 탭 색 통일 |
| P3/남음 | 다수 탭·트리의 제한된 폭 | 가로 스크롤/툴팁 유지. 전체 열린 탭 선택기와 트리 다단계 표시 설정은 후속 작업 |
| P3/남음 | CLI 원본 대화 역할·승인 화면을 완전한 채팅 카드로 표현하기 어려움 | 원본 ANSI 화면 유지. AI별 제목 구분만 강화; 원본 역할을 추측해 다시 쓰지 않음 |
| P3/남음 | 터미널 글꼴과 픽셀 단위 모양 | 글꼴·기본 크기는 Windows Terminal 설정에 따름. GUI와 동일한 라운드/폰트 렌더링은 불가 |

합성 캡처: `workspace/previews/design-before-{120,48}.svg`, `design-after-{120,48}.svg` 및 approval/sidebar/empty/files/git/terminal. `capture-design.py`는 임시 레지스트리와 mock 원본만 사용하고 입력 전송이 없음을 검사한다. 캡처에는 운영 프로젝트·대화를 사용하지 않음. 작은 창의 입력창 잘림은 개선 전 48열 캡처에서 재현된다.

검증: 전체 자동 검사 66개 통과(입력창 화면 내 위치·검색 빈 상태 회귀 검사 포함). 격리 tmux에서 실제 마우스 그룹 이동·Codex 창 닫기·UI 갱신·기존 프로세스 보존 통과. 마우스 통합 검사는 상태 파일 갱신 뒤 화면 배치가 안정될 때까지 기다린 후 좌표를 읽도록 보강. 합성 화면 120×32/48×24와 승인·대기열·보조 패널 캡처 생성 및 육안 검토. 한국어 버튼은 Textual 버튼 내부 여백까지 고려해 최소 폭 확보. SVG를 기준 캡처로 보관(브라우저/호스트 글꼴에 따라 아이콘 모양은 다를 수 있음).
- preview Desktop/Sidebar 반영 완료. 운영 tmux 서버·AI 세션 무변경. 게시용 복사본에 커밋하며 푸시는 관제가 담당.

2026-10-18 남은 탐색 기능 확장

- 열린 탭 선택기: 탭줄 ⌄ 또는 Ctrl+P. 전체 그룹의 열린 탭을 프로젝트 이름으로 검색하고 ↑↓/Enter, 마우스로 선택. Esc 취소. 현재 탭 ●, 고정 ◆, 그룹 번호 표시. 같은 프로젝트의 두 그룹 탭은 서로 다른 탭 ID로 정확히 이동하며 새 세션/AI를 만들지 않음. 0건 안내와 스크롤 제공.
- Files: 선택 폴더에서 펼치기(3단계·40폴더), 접기(선택한 하위 트리 전체). 파일이 선택되어 있으면 부모 폴더 기준. 클릭/화살표로 개별 폴더 탐색도 유지.
- 성능 제한: 지연 읽기, 폴더당 첫 200항목(파일시스템 나열 순서에서 제한 후 정렬), 전체 표시 1,000노드, 최대 깊이 8. .git/node_modules 등 생성 폴더와 심볼릭 링크 제외. 제한은 툴팁/펼치기 알림에 표시. 제한을 넘는 항목의 페이지 탐색은 미구현.
- 폴더 상태: 원본 폴더 경로별로 열림/접힘을 `workspace/data/state/files-expanded.json`에 보관. 프로젝트 전환·새로고침·UI 재시작 후 복원하며 보관 루트 수는 최대 100. 로컬 전용이며 Git 제외. 같은 경로를 공유하는 프로젝트는 펼침 상태도 공유.
- 회귀 검사 추가: 이름 중복/그룹 선택, 한글 검색/0건/취소/키보드, Desktop의 실제 그룹 이동과 tmux 무호출, 폴더 전환/새로고침/접힘 복원, 깊이·항목 수 제한, symlink/생성 폴더 제외. Sidebar 테스트 상태 경로를 임시 폴더로 격리. 상단 배치 테스트는 수동 CSS 모드가 실제 소켓 갱신 타이머에 의해 바뀌지 않도록 고정.
- 합성 전후 캡처: `workspace/previews/navigation-before-tabs.svg`, `navigation-after-tabs.svg`, `navigation-before-files.svg`, `navigation-after-files.svg`. 게시용 이전 소스를 baseline으로 읽어 전후 생성. 임시 폴더/가짜 프로젝트만 사용하며 운영 대화/파일 목록은 포함하지 않음.
- 검증 완료: 전체 69개 검사 통과, 마지막 보강 후 탐색 3개/Sidebar 8개 추가 통과. 격리 tmux Desktop 마우스/재시작/기존 프로세스 보존 통과. preview Desktop·Sidebar 반영 및 생존 확인. 운영 원본에는 키 전송·종료·설정 변경 없음.

2026-10-18 한글 조합 표시 위치 점검
- 사용자 이미지 `/mnt/v/1.images/003.PNG`에서 입력창 왼쪽에 분리된 한글 조합 표시 확인. 공개 저장소에 사용자 이미지를 복사하지 않음. UTF 오류 문구는 보이지 않으며 현 환경의 LANG/LC_ALL/Python 인코딩은 UTF-8.
- 재현: Composer 포커스 후 창 축소 시 실제 입력 커서는 (10,10)인데 Textual app.cursor_position은 이전 (10,27)에 남음. 화면 배치/입력창 크기 변경/선택 변경 뒤 실제 포커스된 Composer 좌표를 동기화하도록 수정. 좌표 일치 회귀 검사 추가, 입력 검사 15개 통과.
- 사용자가 느끼는 입력 지연은 Windows IME 조합부터 화면 출력까지의 실제 경로에서 아직 측정하지 못함. 타이핑은 원본 AI 화면의 0.5초 폴링과 별개로 즉시 처리. 임시 파일에서 합성 초안 저장 20회는 중앙값 0.03ms/최대 0.09ms로 이번 측정에서 저장 지연 재현 없음(실제 Windows 입력 지연 측정값 아님).
- 별도 한글 패키지 설치나 운영 세션 설정 변경은 하지 않음. 실제 Windows IME 표시 위치 및 체감 지연은 사용자 확인 필요.
- 전체 69개 회귀 검사 통과. preview Desktop에 반영 완료.
