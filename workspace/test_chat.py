"""Chat input and CLI events tested without invoking paid AI requests."""
import asyncio
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch
import core
from chat_backend import Conversation

Chat=runpy.run_path(str(core.ROOT/'agent-chat.py'))['Chat']


class BackendTests(unittest.IsolatedAsyncioTestCase):
    async def test_cli_events_resume_and_literal_stdin(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'STATE',Path(tmp)):
            project=dict(id='test',name='Test',path=tmp)
            fake=Path(tmp)/'fake.py'
            fake.write_text('import json,sys\nmessage=sys.stdin.read()\nprint(json.dumps({"type":"thread.started","thread_id":"own-thread"}))\nprint(json.dumps({"type":"item.completed","item":{"type":"agent_message","text":"reply:"+message}}))\n')
            conversation=Conversation(project,'codex')
            with patch.object(conversation,'command',return_value=[sys.executable,str(fake)]):
                answer=await conversation.send('hello; $(anything)',lambda _:None)
            self.assertEqual(answer,'reply:hello; $(anything)')
            self.assertEqual(conversation.session,'own-thread')
            loaded=Conversation(project,'codex')
            self.assertEqual(len(loaded.messages),2)
            with patch('shutil.which',return_value='/bin/codex'):
                command=loaded.command()
                self.assertIn('resume',command)
                self.assertIn('own-thread',command)
                self.assertEqual(command[-1],'-')
            claude=Conversation(project,'claude')
            self.assertEqual(claude.event({'type':'stream_event','session_id':'own-claude','event':{'delta':{'type':'text_delta','text':'안녕'}}}),('안녕',False))
            self.assertEqual(claude.event({'type':'result','result':'안녕하세요'}),('안녕하세요',True))
            with self.assertRaises(RuntimeError): claude.event({'type':'result','is_error':True,'result':'login required'})

    async def test_two_views_cannot_start_same_conversation_at_once(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'STATE',Path(tmp)):
            project=dict(id='test',path=tmp)
            first=Conversation(project,'codex'); second=Conversation(project,'codex')
            with patch.object(first,'command',return_value=[sys.executable,'-c','import time; time.sleep(30)']):
                request=asyncio.create_task(first.send('hello',lambda _:None))
                while first.process is None: await asyncio.sleep(.01)
                with self.assertRaises(ValueError): await second.send('another',lambda _:None)
                first.stop()
                with self.assertRaises(RuntimeError): await asyncio.wait_for(request,3)

    async def test_own_process_can_be_stopped(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'STATE',Path(tmp)):
            conversation=Conversation(dict(id='test',path=tmp),'codex')
            with patch.object(conversation,'command',return_value=[sys.executable,'-c','import time; time.sleep(30)']):
                request=asyncio.create_task(conversation.send('hello',lambda _:None))
                while conversation.process is None: await asyncio.sleep(.01)
                conversation.stop()
                with self.assertRaises(RuntimeError): await asyncio.wait_for(request,3)
                self.assertIsNone(conversation.process)


class ChatUITests(unittest.IsolatedAsyncioTestCase):
    async def test_enter_send_shift_enter_newline_and_reply(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'STATE',Path(tmp)),patch.object(core,'set_status'),patch.object(core,'tmux'):
            project=dict(id='test',name='MyProject',path=tmp)
            conversation=Conversation(project,'codex')
            async def send(message,on_text):
                conversation.messages.append({'role':'user','text':message})
                on_text('안녕하세요')
                conversation.messages.append({'role':'assistant','text':'안녕하세요'})
            with patch.object(conversation,'send',side_effect=send) as request:
                app=Chat(project,'codex',conversation)
                async with app.run_test(size=(74,18)) as pilot:
                    await pilot.pause()
                    editor=app.query_one('#message')
                    editor.insert('첫 줄')
                    await pilot.press('shift+enter')
                    editor.insert('다음 줄')
                    self.assertIn('\n',editor.text)
                    await pilot.press('enter')
                    await pilot.pause()
                    request.assert_called_once()
                    self.assertEqual(request.call_args.args[0],'첫 줄\n다음 줄')
                    self.assertIn('안녕하세요',str(app.query_one('#messages').render()))
                    self.assertFalse(app.busy)
                    await pilot.resize_terminal(34,9)
                    await pilot.pause()
                    self.assertTrue(app.screen.has_class('compact'))
                    self.assertGreater(app.query_one('#message').region.height,0)
