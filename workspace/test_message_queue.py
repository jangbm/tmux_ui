import unittest
from message_queue import MessageQueue

IDLE=dict(id='%3',pid='10',state='idle',menu=False)
BUSY={**IDLE,'state':'busy'}

class QueueTests(unittest.TestCase):
    def test_requires_explicit_resume_and_pauses_after_restart(self):
        q=MessageQueue();q.add('hello','%3','10')
        self.assertFalse(q.ready(IDLE));q.resume(IDLE)
        self.assertTrue(q.ready(IDLE))
        restored=MessageQueue(q.items)
        self.assertFalse(restored.ready(IDLE))
    def test_waits_for_work_to_finish_then_dispatches(self):
        q=MessageQueue();q.add('next','%3','10');q.resume(BUSY)
        self.assertFalse(q.ready(BUSY));self.assertTrue(q.ready(IDLE))
    def test_menu_draft_disconnect_and_replacement_pause(self):
        for state in ({**IDLE,'menu':True},{**IDLE,'state':'waiting'},{**IDLE,'state':'unknown'},{**IDLE,'pid':'11'},{**IDLE,'id':'%4'}):
            q=MessageQueue();q.add('next','%3','10');q.resume(BUSY)
            self.assertFalse(q.ready(state));self.assertFalse(q.armed)
            self.assertFalse(q.ready(IDLE));self.assertEqual(len(q.items),1)
    def test_uncertain_attempt_never_retries_automatically(self):
        q=MessageQueue([dict(text='sent?',pane='%3',pid='10',attempted=True)])
        with self.assertRaises(ValueError): q.resume(IDLE)
        q.armed=True
        self.assertFalse(q.ready(IDLE));self.assertEqual(q.items[0]['text'],'sent?')
