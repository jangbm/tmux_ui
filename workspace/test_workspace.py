"""Regression checks using temporary projects; never connect to a tmux server."""
import asyncio
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
import core
from sidebar import Sidebar, ProjectFiles, ProjectTab
from textual.widgets import Input, TabbedContent


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='tmux-ui-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.config=patch.object(core,'CONFIG',self.root/'projects.json')
        self.config.start(); self.addCleanup(self.config.stop)

    def git(self,*args):
        result=core.run(['git','-C',str(self.root),*args])
        self.assertEqual(result.returncode,0,result.stderr)

    def test_import_preserves_files_and_does_not_create_git(self):
        (self.root/'한글.txt').write_text('내용')
        before=set(self.root.iterdir())
        core.add('한글 프로젝트',self.root,key='korean',mode='import',git=True)
        self.assertEqual((self.root/'한글.txt').read_text(),'내용')
        self.assertEqual(set(self.root.iterdir())-before,
                         {self.root/'projects.json',self.root/'projects.json.lock'})
        self.assertFalse((self.root/'.git').exists())
        with self.assertRaises(ValueError):
            core.add('Duplicate',self.root,key='duplicate',mode='import')

    def test_git_counts_staged_unstaged_untracked_and_rename(self):
        self.git('init')
        old=self.root/'old.txt'; old.write_text('before\n')
        self.git('add','old.txt')
        self.git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','initial')
        self.git('mv','old.txt','이름 변경.txt')
        (self.root/'이름 변경.txt').write_text('before\nafter\n')
        (self.root/'untracked.txt').write_text('new')
        before=(self.root/'.git/index').read_bytes()
        snapshot=core.git_snapshot(self.root)
        self.assertEqual(snapshot['staged'],1)
        self.assertEqual(snapshot['modified'],1)
        self.assertEqual(snapshot['untracked'],1)
        self.assertIn(('RM','이름 변경.txt'),snapshot['files'])
        self.assertEqual((self.root/'.git/index').read_bytes(),before)

    def test_preview_bounds_binary_and_outside_paths(self):
        file=self.root/'test.txt'; file.write_text('한글')
        self.assertEqual(core.preview_text(self.root,file),'한글')
        file.write_bytes(b'x'*300000)
        self.assertIn('Preview limited',core.preview_text(self.root,file))
        file.write_bytes(b'\0binary')
        with self.assertRaises(ValueError): core.preview_text(self.root,file)
        with tempfile.TemporaryDirectory() as other:
            outside=Path(other)/'other.txt'; outside.write_text('outside')
            link=self.root/'link'; link.symlink_to(outside)
            with self.assertRaises(ValueError): core.preview_text(self.root,link)


class SidebarTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        tmux=patch.object(core,'tmux',return_value=__import__('subprocess').CompletedProcess([],0,'',''))
        tmux.start(); self.addCleanup(tmux.stop)
        collector=patch('watcher.refresh',return_value=False)
        collector.start()
        self.addCleanup(collector.stop)

    async def test_compact_terminal_buttons_use_selected_shell_and_hide(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(core,'CONFIG',root/'projects.json'), \
                 patch.dict(os.environ,{'TMW_PROJECT':'buttons'}), \
                 patch('layout.terminals',return_value=[]), \
                 patch('layout.show_terminal') as show:
                core.add('Buttons',root/'project',key='buttons')
                app=Sidebar()
                async with app.run_test(size=(34,23)) as pilot:
                    await pilot.pause()
                    app.query_one('#views',TabbedContent).active='terminal-view'
                    app.query_one('#shell-kind').focus()
                    await pilot.pause()
                    app.query_one('#shell-kind').value='cmd'
                    await pilot.click('#new-terminal')
                    self.assertEqual(show.call_args.kwargs,{'kind':'cmd','new':True})
                    await pilot.click('#hide-terminal')
                    self.assertEqual(show.call_args.kwargs,{'kind':'cmd','hide':True})

    async def test_import_and_files_git_tabs_at_small_and_large_sizes(self):
        with tempfile.TemporaryDirectory(prefix='tmux-ui-ui-') as tmp:
            root=Path(tmp)
            project=root/'existing'; project.mkdir()
            (project/'hello.txt').write_text('hello')
            (project/'.venv').mkdir()
            with patch.object(core,'CONFIG',root/'projects.json'), \
                 patch.object(core,'STATE',root/'state'), \
                 patch.dict(os.environ,{'TMW_PROJECT':'existing'}):
                for size in ((34,47),(34,23)):
                    # First size exercises import; second reuses the registry.
                    app=Sidebar()
                    async with app.run_test(size=size) as pilot:
                        await pilot.press('i')
                        await pilot.pause()
                        self.assertTrue(app.query_one('#existing').value)
                        self.assertTrue(app.query_one('#git').disabled)
                        if not core.projects():
                            app.query_one('#name',Input).value='한글 프로젝트'
                            app.query_one('#project-id',Input).value='existing'
                            app.query_one('#path',Input).value=str(project)
                            app.query_one('#use-codex').value=False
                            with patch.object(core,'create_session') as create,patch('editor_tabs.initialize'):
                                app.query_one('#create').press()
                                await pilot.pause()
                                create.assert_called_once()
                            self.assertEqual(len(core.projects()),1)
                            self.assertFalse(core.projects()[0]['agents']['codex'])
                            self.assertFalse((project/'.git').exists())
                        else:
                            await pilot.press('escape')
                        app.query_one('#views',TabbedContent).active='files-view'
                        await pilot.pause()
                        tree=app.query_one('#files',ProjectFiles)
                        self.assertEqual(tree.path,project)
                        self.assertEqual([p.name for p in tree.filter_paths(project.iterdir())],['hello.txt'])
                        app.query_one('#views',TabbedContent).active='git-view'
                        await pilot.pause()
                        worker=app.refresh_git()
                        await asyncio.wait_for(worker.wait(),5)
                        self.assertIn('not a repository',str(app.query_one('#git-status').render()))
                        app.action_agent_settings()
                        await pilot.pause()
                        self.assertFalse(app.query_one('#show-codex').value)
                        app.query_one('#show-codex').value=True
                        with patch('layout.set_agents') as configure:
                            app.query_one('#apply-agents').press()
                            await pilot.pause()
                            configure.assert_called_once()
                            self.assertEqual(configure.call_args.args[1],{'claude':True,'codex':True})

    async def test_project_tabs_click_drag_scroll_and_footer_docking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(core,'CONFIG',root/'projects.json'), patch.dict(os.environ,{'TMW_PROJECT':'p0'}):
                for index in range(12): core.add(f'Project {index}',root/str(index),key=f'p{index}',claude=False,codex=False)
                app=Sidebar()
                async with app.run_test(size=(70,35)) as pilot:
                    await pilot.pause()
                    self.assertFalse(app.query_one('#project-tabs').display)
                    self.assertEqual(app.query_one('#new-project').parent.parent.id,'projects-view')
                    app.screen.add_class('top')
                    await pilot.pause()
                    tabs=list(app.query(ProjectTab))
                    with patch.object(app,'open_project') as opened:
                        await pilot.click(tabs[0])
                        opened.assert_called_once_with('p0')
                    await pilot.mouse_down(tabs[1])
                    await pilot.mouse_up(tabs[0])
                    await pilot.pause()
                    self.assertEqual([p['id'] for p in core.projects()][:2],['p1','p0'])
                    tabs=list(app.query(ProjectTab))
                    await pilot.mouse_down(tabs[0])
                    await pilot.mouse_up(tabs[2])
                    await pilot.pause()
                    self.assertEqual([p['id'] for p in core.projects()][:3],['p0','p2','p1'])
                    self.assertGreater(app.query_one('#project-tabs').max_scroll_x,0)
                    self.assertFalse(list(app.query('#split-target, #workspace-tools, #split-right, #split-below, #close-split')))
                    self.assertEqual(app.query_one('#dock-top').parent.id,'dock-tools')
                    self.assertGreater(app.query_one('#dock-tools').region.y,app.query_one('#tree').region.y)
                    with patch('layout.dock_workspace') as dock:
                        await pilot.click('#dock-top')
                        self.assertEqual(dock.call_args.args[1],'top')
                        await pilot.click('#dock-left')
                        self.assertEqual(dock.call_args.args[1],'left')
                    app.screen.add_class('top')
                    await pilot.resize_terminal(100,16)
                    await pilot.pause()
                    self.assertGreater(app.query_one('#project-tabs').max_scroll_x,0)

    async def test_file_preview_is_read_only(self):
        FilePreview=runpy.run_path(str(core.ROOT/'file-preview.py'))['FilePreview']
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'한글.txt'; file.write_text('original')
            app=FilePreview(tmp,file)
            async with app.run_test(size=(90,30)) as pilot:
                await pilot.press('x','y')
                self.assertTrue(app.query_one('#contents').read_only)
                self.assertEqual(app.query_one('#contents').text,'original')
            self.assertEqual(file.read_text(),'original')


if __name__=='__main__': unittest.main()
