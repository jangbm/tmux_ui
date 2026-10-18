# tmux_ui (워커)

워커 PC(WSL) tmux의 화면·사용성 개선 프로젝트. 2026-10-18 관제(control)가 세팅했고, Codex가 이 tmux 세션(`tmux_ui`)에서 작업한다.

## 목표 (출처: cont `infra/워커PC_세팅.md` 3-4절 "tmux UI/UX 개선안")
1. **상태바에 전체 세션 상태**: 예) `unity ⚙ │ ebook ⏸ │ stock ✓ │ loop 3/6`
   - ⚙ 작업 중: 화면에 `esc to interrupt`
   - ⏸ 사용자 답 대기: 질문·권한 확인 화면(선택지 목록, `Do you want`, `❯ 1.` 등)
   - ✓ 쉼: 입력창 비어 있음. `❯` 뒤 흐린 글씨(`ESC[2m`)는 자동 추천이라 입력이 아니다(`tmux capture-pane -e`로 구분).
   - loop: `/mnt/d/projects/kid_app_loop/loop/runs/runner_state.json`의 state·laps_today
   - 5~10초마다 스크립트(`bin/`)가 계산해 파일에 쓰고, 상태바는 `#(cat 파일)`로 읽기만 한다(상태바 갱신마다 capture-pane을 돌리지 않게).
2. **세션별 색**: 상태바 색을 Windows Terminal 탭 색과 맞춤
   video #C0504D · gaussian #4F81BD · unity #9BBB59 · print3d #F79646 · control #8064A2 · marketing #4BACC6 · design #2F8F82 · ebook #B5577A · stock #D4A017 · tmux_ui #5B6B7A
3. **복사 개선**: 마우스 모드에서 드래그 선택 → Windows 클립보드(`clip.exe`, UTF-8 한글 깨짐 주의)
- 선택: 4) `Ctrl+b s` 세션 목록 미리보기 팝업, 5) Ctrl+D·`exit` 실수로 세션 종료 방지

## 파일
- `tmux.conf` — 이 프로젝트의 설정. `~/.tmux.conf` 맨 끝에서 `source-file -q ~/projects/tmux_ui/tmux.conf`로 읽는다(관제가 연결해 둠). **`~/.tmux.conf` 원본은 고치지 않는다.**
- `tmux.conf.orig` — 시작 시점 `~/.tmux.conf` 사본(되돌리기용).
- `bin/` — 상태 계산 스크립트. `NOTES.md` — 결정·시험 기록.

## 원칙 (중요)
- 지금 tmux에 control·unity·ebook·stock·marketing·loop 등 **24시간 작업 세션이 돌고 있다.** 세션을 죽이거나(kill-server, kill-session) 다른 세션에 키를 보내지 않는다(send-keys 금지).
- 새 설정은 먼저 **별도 서버**에서 시험: `tmux -L test -f tmux.conf new -d -s t` … 확인 후 `tmux -L test kill-server`. 통과한 뒤에만 실제 서버에 `tmux source-file ~/.tmux.conf`.
- 문제가 생기면 `tmux.conf`를 비우고 `tmux source-file ~/.tmux.conf`로 되돌린다.
- 상태 스크립트는 가볍게(전체 1초 안), 실패해도 상태바가 깨지지 않게.
- 사용자 보고는 한국어로 짧게. git은 이 폴더 로컬 커밋만(원격 없음).

## 관제의 UI 공동 수정 (사용자 추가 요청)
- control도 `/home/jang/projects/tmux_ui`의 UI 소스를 수정·검증·적용할 수 있다.
- 구체적인 파일과 검증·적용 명령은 [CONTROL_UI.md](CONTROL_UI.md)를 따른다.
- 다른 작업자의 변경사항과 저장된 초안을 보존한다. 운영 AI에 테스트 키를 보내거나 세션을 종료하지 않는다.
- 도구의 작업 폴더 제한은 이 문서가 변경하지 않는다. 제한이 있으면 이 저장소를 해당 도구의 작업 범위에 추가해야 한다.
