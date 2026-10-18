"""Own CLI conversations only. Never attaches to or sends input to tmux panes."""
import asyncio
import json
import os
import signal
import shutil
import fcntl
import core


class Conversation:
    def __init__(self,project,agent):
        if agent not in core.AGENTS: raise ValueError('Unknown agent')
        self.project=project; self.agent=agent; self.session=None; self.messages=[]; self.process=None
        self.path=core.STATE/'chats'/f"{project['id']}-{agent}.json"
        try:
            data=json.loads(self.path.read_text())
            self.session=data.get('session')
            self.messages=data.get('messages',[])[-100:]
        except (OSError,ValueError): pass
    def save(self):
        core.atomic(self.path,{'session':self.session,'messages':self.messages[-100:]})
    def command(self):
        executable=shutil.which(self.agent)
        if not executable: raise ValueError(self.agent.title()+' CLI가 설치되지 않았습니다')
        if self.agent=='codex':
            args=[executable,'-a','never','-s','workspace-write','exec','--json','--skip-git-repo-check','--color','never']
            if self.session: args+=['resume',self.session]
            return [*args,'-']
        args=[executable,'--print','--output-format','stream-json','--verbose','--include-partial-messages',
              '--permission-mode','dontAsk']
        if self.session: args+=['--resume',self.session]
        return args
    def event(self,event):
        """Return display text and whether it replaces accumulated assistant text."""
        kind=event.get('type')
        if self.agent=='codex':
            if kind=='thread.started': self.session=event.get('thread_id',self.session)
            if kind=='item.completed' and event.get('item',{}).get('type')=='agent_message':
                return event['item'].get('text',''),False
            if kind in ('turn.failed','error'):
                value=event.get('error',event)
                raise RuntimeError(value.get('message','Codex 요청 실패') if isinstance(value,dict) else str(value))
        else:
            self.session=event.get('session_id',self.session)
            if kind=='stream_event':
                delta=event.get('event',{}).get('delta',{})
                if delta.get('type')=='text_delta': return delta.get('text',''),False
            if kind=='result':
                if event.get('is_error'): raise RuntimeError(event.get('result') or '\n'.join(event.get('errors',[])) or 'Claude 요청 실패')
                return event.get('result',''),True
        return '',False
    async def send(self,message,on_text):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.with_suffix('.lock').open('a') as lock:
            try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError: raise ValueError('같은 프로젝트의 이 AI가 다른 창에서 답변 중입니다.')
            try:
                if self.path.exists():
                    stored=Conversation(self.project,self.agent)
                    self.session=stored.session; self.messages=stored.messages
                return await self._send(message,on_text)
            finally: fcntl.flock(lock,fcntl.LOCK_UN)
    async def _send(self,message,on_text):
        if self.process: raise ValueError('이미 답변 중입니다')
        command=self.command()
        self.messages.append({'role':'user','text':message}); self.save()
        text=''; stderr=bytearray()
        async def read_errors():
            while chunk:=await self.process.stderr.read(4096):
                stderr.extend(chunk)
                if len(stderr)>16384: del stderr[:-16384]
        try:
            self.process=await asyncio.create_subprocess_exec(*command,cwd=self.project['path'],
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,
                start_new_session=True,limit=2*1024*1024)
            errors=asyncio.create_task(read_errors())
            try:
                self.process.stdin.write(message.encode()); await self.process.stdin.drain(); self.process.stdin.close()
                while raw:=await self.process.stdout.readline():
                    try: event=json.loads(raw)
                    except (ValueError,UnicodeDecodeError): continue
                    value,replace=self.event(event)
                    if value:
                        text=value if replace else text+value
                        on_text(text)
                code=await self.process.wait(); await errors
                if code: raise RuntimeError(stderr.decode(errors='replace').strip()[-1500:] or f'{self.agent} 종료 코드 {code}')
                if not text: raise RuntimeError('응답이 없습니다. CLI 로그인 상태를 확인해 주세요.')
                self.messages.append({'role':'assistant','text':text}); self.save()
                return text
            finally:
                if self.process.returncode is None:
                    self.stop()
                    try: await asyncio.wait_for(self.process.wait(),3)
                    except asyncio.TimeoutError:
                        try: os.killpg(self.process.pid,signal.SIGKILL)
                        except ProcessLookupError: pass
                        await self.process.wait()
                if not errors.done(): errors.cancel()
                await asyncio.gather(errors,return_exceptions=True)
        finally:
            self.process=None
            self.save()
    def stop(self):
        if self.process and self.process.returncode is None:
            try: os.killpg(self.process.pid,signal.SIGTERM)
            except ProcessLookupError: pass
