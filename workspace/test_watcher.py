"""Status detection regressions; no live tmux connection or agent launch."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch
import core
import watcher


class DetectionTests(unittest.TestCase):
    def test_busy_and_permissions(self):
        self.assertEqual(watcher.detect('Working…\nesc to interrupt\n',1)[0],'busy')
        screen='Do you want to allow this?\n❯ 1. Yes\n  2. No\nesc to interrupt'
        self.assertEqual(watcher.detect(screen,1),('waiting','choice'))
        self.assertEqual(watcher.detect('Continue [y/n]?',0)[0],'waiting')

    def test_dim_suggestion_is_not_input(self):
        for suggestion in ('Yes, continue','1. 다음 작업','Allow edits'):
            self.assertEqual(watcher.detect('  ❯ \x1b[2m'+suggestion+'\x1b[0m',0),('idle','empty-prompt'))
        for prompt in ('❯','›'):
            screen=prompt+' \x1b[2mSuggested next step\x1b[0m'
            self.assertEqual(watcher.detect(screen,0),('idle','empty-prompt'))
        screen='\x1b[2mheading\n› \x1b[38;2;0;0;0mSuggestion\x1b[22m'
        self.assertEqual(watcher.detect(screen,1),('idle','empty-prompt'))

    def test_user_draft_and_old_choices(self):
        screen='› real input\x1b[2m suggested suffix\x1b[0m'
        self.assertEqual(watcher.detect(screen,0),('waiting','draft'))
        screen='❯ 1. An old example\n'+'output\n'*15+'› '
        self.assertEqual(watcher.detect(screen,16),('idle','empty-prompt'))
        self.assertEqual(watcher.detect('› explain esc to interrupt',0),('waiting','draft'))

    def test_shell_and_unrecognized_are_never_guessed_done(self):
        self.assertEqual(watcher.detect('Old output\nesc to interrupt',1,agent_running=False),('unknown','not-running'))
        self.assertEqual(watcher.detect('No new output',0)[0],'unknown')
        self.assertEqual(watcher.detect('',0)[0],'unknown')
        self.assertEqual(watcher.detect('',0,dead=True),('error','pane-exited'))


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='tmux-ui-status-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        for name,value in (('STATE',self.root/'state'),('CONFIG',self.root/'projects.json')):
            item=patch.object(core,name,value); item.start(); self.addCleanup(item.stop)
        core.add('Demo',self.root/'project',key='demo')

    def snapshot(self,state='waiting',updated=None,changed=None):
        now=time.time() if updated is None else updated
        watcher.core.atomic(watcher.observed_path(),{'updated':now,'projects':{'demo':{'codex':{
            'state':state,'detail':'choice','updated':now,'changed_at':changed or now,'source':'screen'}}}})

    def test_shared_cache_acknowledgement_and_read_only_collection(self):
        screen='› \x1b[2mSuggestion\x1b[0m'
        def respond(command,**kwargs):
            if 'list-panes' in command:
                return SimpleNamespace(returncode=0,stdout='tw-demo|%1|codex|codex|123|0|0\n')
            if 'capture-pane' in command:
                return SimpleNamespace(returncode=0,stdout=screen)
            self.fail('Unexpected tmux operation: '+repr(command))
        with patch.object(core,'run',side_effect=respond) as calls:
            self.assertTrue(watcher.refresh())
            self.assertFalse(watcher.refresh())
            self.assertEqual(calls.call_count,2)
            self.assertEqual(core.status()['demo']['codex']['state'],'idle')
            self.assertLess(watcher.read_snapshot()['elapsed'],1)
            screen='❯ 1. Yes\n  2. No'
            watcher.refresh(force=True)
            self.assertFalse(core.status()['demo']['codex']['seen'])
            core.mark_seen('demo','codex')
            self.assertTrue(core.status()['demo']['codex']['seen'])
            watcher.refresh(force=True)
            self.assertTrue(core.status()['demo']['codex']['seen'])

    def test_stale_busy_becomes_unknown(self):
        self.snapshot('busy',updated=time.time()-60)
        self.assertEqual(core.status()['demo']['codex']['state'],'unknown')
        self.assertEqual(core.status()['demo']['codex']['detail'],'stale-monitor')

    def test_manual_hook_can_report_done_until_new_observed_transition(self):
        now=time.time()
        self.snapshot('idle',updated=now,changed=now-10)
        core.set_status('demo','codex','done')
        self.assertEqual(core.status()['demo']['codex']['state'],'done')
        self.snapshot('busy',changed=time.time()+1)
        self.assertEqual(core.status()['demo']['codex']['state'],'busy')

    def test_timeout_and_invalid_snapshot_fail_gracefully(self):
        self.snapshot('busy')
        old=watcher.observed_path().read_bytes()
        with patch.object(core,'run',side_effect=OSError('unavailable')):
            self.assertFalse(watcher.refresh(force=True))
        self.assertEqual(watcher.observed_path().read_bytes(),old)
        core.atomic(watcher.observed_path(),{'updated':'bad','projects':[]})
        self.assertEqual(watcher.read_snapshot(),{})


if __name__=='__main__': unittest.main()
