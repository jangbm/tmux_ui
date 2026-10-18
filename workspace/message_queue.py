"""Pane-pinned, explicit message scheduling. Restored queues always pause."""
class MessageQueue:
    def __init__(self,items=None):
        self.items=list(items or []);self.armed=False;self.saw_busy=False
    def add(self,text,pane,pid):
        self.items.append(dict(text=text,pane=pane,pid=pid))
    def pause(self): self.armed=False;self.saw_busy=False
    def resume(self,current):
        if not self.items: return
        first=self.items[0]
        if first.get('attempted'):
            raise ValueError('전송을 시도했던 메시지입니다. 원본 도착 여부를 확인하고 수정 버튼으로 가져와 주세요.')
        if (first['pane'],first['pid'])!=(current.get('id'),current.get('pid')):
            raise ValueError('대기열의 원본 AI 연결이 바뀌었습니다. 내용을 수정 입력창으로 가져와 다시 등록해 주세요.')
        if current.get('state') not in ('idle','busy') or current.get('menu'):
            raise ValueError('승인·질문·원본 입력을 처리한 뒤 대기열을 시작해 주세요.')
        self.armed=True;self.saw_busy=current['state']=='idle'
    def ready(self,current):
        if not self.items or not self.armed: return False
        first=self.items[0]
        if first.get('attempted'): self.pause();return False
        if (first['pane'],first['pid'])!=(current.get('id'),current.get('pid')) or current.get('menu') or current.get('state') not in ('idle','busy'):
            self.pause();return False
        if current['state']=='busy': self.saw_busy=True;return False
        return self.saw_busy
