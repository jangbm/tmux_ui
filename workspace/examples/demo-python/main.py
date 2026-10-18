"""Small task board demo. Run: python3 main.py"""
from dataclasses import dataclass


@dataclass
class Task:
    title: str
    done: bool = False


class TaskBoard:
    def __init__(self):
        self.tasks: list[Task] = []

    def add(self, title: str):
        self.tasks.append(Task(title))

    def complete(self, index: int):
        self.tasks[index].done = True

    def render(self) -> str:
        return '\n'.join(
            f"{'✓' if task.done else '○'} {task.title}"
            for task in self.tasks
        )


if __name__ == '__main__':
    board = TaskBoard()
    board.add('프로젝트 탭 전환')
    board.add('좌우·상하 분할 확인')
    board.add('탭 순서 드래그 / 상단 높이 조절')
    board.complete(0)
    print(board.render())
