# tmux_ui

WSL의 tmux Claude/Codex 세션을 프로젝트 탭과 분할 대화창으로 관리하는 Textual UI입니다.

- 프로젝트별 탭 이동·분할, 사이드바와 대화창 크기 조절
- 기존 tmux AI 세션의 화면·메시지 연결, 승인 메뉴 키보드 조작
- 작업·승인 대기·미확인 결과 표시
- 텍스트 선택 및 Windows 클립보드 복사
- AI별 응답 중지, 대화창 숨기기, 확인 후 종료

## 실행

Python 3.10 이상, tmux, 실행할 Claude/Codex CLI가 필요합니다. 현재 개발 환경은 Python 3.14, tmux 3.6, Textual 7.5.0입니다. 일부 설정에는 개발 PC의 절대 경로가 들어 있으므로 다른 PC에서는 조정이 필요합니다.

```bash
git clone https://github.com/jangbm/tmux_ui.git
cd tmux_ui/workspace
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python core.py add "MyProject" ./data/MyProject --id myproject --git --start
./launch.sh
```

UI는 별도 tmux 서버 `tmux-ui-preview`에서 실행합니다. 로컬 프로젝트 설정, 대화 기록, 초안과 가상환경은 Git에 포함하지 않습니다.

자세한 사용법과 제한은 [workspace/README.md](workspace/README.md), 개발·검증 기록은 [NOTES.md](NOTES.md)를 참고하세요.

## 검사

```bash
workspace/.venv/bin/python -m unittest discover -s workspace -v
workspace/.venv/bin/python workspace/check-session-input.py
TMW_SOCKET=tmux-ui-test workspace/.venv/bin/python workspace/check-desktop.py
```

통합 검사는 별도 테스트 tmux 서버에서 실행합니다.
