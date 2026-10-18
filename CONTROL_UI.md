# 관제의 tmux UI 공동 수정

사용자 요청: 관제(control)도 이 UI 소스를 직접 수정하고 검증·적용할 수 있다.

## 소스와 범위

- 공용 저장소: `/home/jang/projects/tmux_ui`
- UI: `workspace/desktop-app.py`, `workspace/desktop.tcss`, `workspace/sidebar.py`
- 프로젝트 자동 발견/상태: `workspace/live_tmux.py`
- 사용자가 선택한 원본 AI 입력: `workspace/session_input.py`
- 개발 안내: 이 저장소의 `AGENTS.md`와 `workspace/README.md`
- 로컬 프로젝트·초안·대화: `workspace/data/` (Git 제외, 임의 삭제 금지)

관제와 개발자가 같은 파일을 사용한다. 작업 전 diff를 읽고 기존 수정사항을 보존한다. 여러 에이전트가 같은 파일을 동시에 고치지 않도록 담당 범위를 조율한다. 운영 tmux 세션 종료나 테스트용 입력 전송은 하지 않는다. 폴더 신뢰 확인을 자동 승인하지 않는다.

파일의 OS 쓰기 권한과 AI 실행 도구의 작업 폴더 제한은 별개다. 관제 도구가 이 경로 쓰기를 거부하면 해당 도구에 이 저장소를 작업 폴더로 추가하거나 이 저장소에서 편집 세션을 연다. 이 문서는 실행 중인 에이전트의 샌드박스 권한을 바꾸지 않는다.

## 검사 및 적용

```bash
cd /home/jang/projects/tmux_ui
workspace/.venv/bin/python -m unittest discover -s workspace -v
workspace/.venv/bin/python workspace/check-session-input.py
workspace/.venv/bin/python workspace/check-clipboard.py
TMW_SOCKET=tmux-ui-test workspace/.venv/bin/python workspace/check-desktop.py
```

변경 범위와 관련된 검사만 선택해서 실행해도 된다. 통합 검사는 격리 서버만 사용한다.

```bash
# 프로젝트·AI 연결 상태 확인 (원본에는 읽기만 수행)
workspace/.venv/bin/python workspace/ui-maintenance.py status
# 자동 감지 주기를 기다리지 않고 새 세션 등록
workspace/.venv/bin/python workspace/ui-maintenance.py discover
# Desktop 소스 변경 적용: 초안 저장/전송 잠금 확인 후 preview UI만 다시 실행
workspace/.venv/bin/python workspace/ui-maintenance.py reload
# 사이드바 소스 변경 적용
workspace/.venv/bin/python workspace/refresh-style.py
```

`test`처럼 새로 생성된 원본 tmux 세션은 자동 감지 주기에 사이드바에 나타난다. 각 pane의 전면 Claude/Codex를 연결하며 신뢰 확인 화면도 기존 원본에서 표시한다. 관제 명령을 UI가 해석하여 AI를 새로 실행하는 기능은 아니다. 관제가 만든 실제 세션을 발견하여 연결한다.

Git 원격 업로드는 사용자 요청 범위에서만 한다. 현재 환경의 `.git` 읽기 전용 또는 GitHub 인증 실패를 소스 편집 권한으로 혼동하지 않는다.

## 삭제 범위

사용자는 관제도 UI 소스의 수정·삭제를 수행할 수 있음을 확인했다. 요청 범위에서 불필요한 UI 파일을 정리하되 기존 사용자 변경사항을 보존한다. 사이드바에서 숨기기, AI 프로세스 종료, 실제 프로젝트 디렉터리 삭제, tmux 세션 삭제는 각각 별도의 작업이다. 단순 UI 항목 제거를 원본 데이터·운영 세션 삭제로 확대 해석하지 않는다. 현재 `ui-maintenance.py`에는 삭제 명령이 없으며 숨기기/AI 종료는 기존 UI 기능을 사용한다.
