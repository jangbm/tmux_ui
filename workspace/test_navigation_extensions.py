import tempfile
import unittest
import runpy
from desk_state import DeskState
from pathlib import Path
from unittest.mock import patch
from textual.app import App
from textual.widgets import Input, OptionList
from open_tabs import OpenTabs
from file_tree import ProjectFiles
import core

class NavigationTests(unittest.IsolatedAsyncioTestCase):
    async def test_tab_search_keyboard_duplicates_empty_and_cancel(self):
        app=App();result=[]
        rows=[dict(id=str(i),name='동일 프로젝트' if i<2 else 'Other',group=i+1,pinned=i==0) for i in range(3)]
        async with app.run_test(size=(48,20)) as pilot:
            app.push_screen(OpenTabs(rows,'0'),result.append);await pilot.pause()
            app.screen.query_one(Input).value='동일';await pilot.pause()
            self.assertEqual(app.screen.query_one(OptionList).option_count,2)
            await pilot.press('down','enter');await pilot.pause()
            self.assertEqual(result,['1'])
            app.push_screen(OpenTabs(rows,'0'),result.append);await pilot.pause()
            await pilot.resize_terminal(28,14);await pilot.pause()
            self.assertGreater(app.screen.query_one(OptionList).region.height,0)
            app.screen.query_one(Input).value='missing';await pilot.pause()
            await pilot.press('enter');self.assertIsInstance(app.screen,OpenTabs)
            await pilot.press('escape');await pilot.pause();self.assertEqual(result,['1',None])
    async def test_desktop_picker_selects_exact_group_without_tmux(self):
        Desktop=runpy.run_path(str(core.ROOT/'desktop-app.py'))['Desktop']
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'CONFIG',Path(tmp)/'projects.json'),patch.object(core,'STATE',Path(tmp)/'state'),patch.object(core,'tmux') as tmux:
            project=dict(id='sample',name='Sample',path=tmp,agents={'claude':False,'codex':False})
            core.atomic(core.CONFIG,[project]);state=DeskState();first=state.open('sample');second=state.split(first['id'],copy=True)
            app=Desktop(project,state.value,publish=False)
            async with app.run_test(size=(80,24)) as pilot:
                await pilot.pause();await pilot.press('ctrl+p');await pilot.pause()
                await pilot.press('up','enter');await pilot.pause()
                self.assertEqual(app.state.group()['active'],first['id'])
                self.assertNotEqual(first['id'],second['id']);tmux.assert_not_called()

    async def test_file_expansion_persists_switch_reload_and_limits(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'STATE',Path(tmp)/'state'):
            root=Path(tmp)/'one';other=Path(tmp)/'two';other.mkdir();(root/'a'/'b'/'c'/'d').mkdir(parents=True)
            for i in range(15): (root/'a'/f'{i}.txt').touch()
            (root/'node_modules').mkdir();(root/'external').symlink_to(other,target_is_directory=True)
            class FilesApp(App):
                def compose(self): yield ProjectFiles(root,id='files')
            app=FilesApp()
            async with app.run_test() as pilot:
                await pilot.pause(.4);tree=app.query_one(ProjectFiles)
                tree.move_cursor(tree.root);await tree.expand_levels().wait();await pilot.pause()
                self.assertTrue(next(n for n in tree.nodes() if n.data.path==root/'a'/'b').is_expanded)
                self.assertFalse(any(n.data.path.name in ('external','node_modules') for n in tree.nodes()))
                await tree.reload();await pilot.pause()
                self.assertTrue(next(n for n in tree.nodes() if n.data.path==root/'a').is_expanded)
                tree.path=other;await pilot.pause(.3);tree.path=root;await pilot.pause(.5)
                self.assertTrue(next(n for n in tree.nodes() if n.data.path==root/'a'/'b').is_expanded)
                tree.move_cursor(tree.root);await tree.collapse_levels().wait();await pilot.pause()
                self.assertFalse(tree.root.is_expanded)
                tree.path=other;await pilot.pause(.2);tree.path=root;await pilot.pause(.3)
                self.assertFalse(tree.root.is_expanded)
                tree.MAX_ENTRIES=5;tree.MAX_NODES=9;tree.MAX_DEPTH=2
                await tree.reload();await tree.expand_levels().wait();await pilot.pause()
                self.assertLessEqual(sum(1 for n in tree.nodes()),9)
                self.assertTrue(tree.limited)
                self.assertTrue(all(not n.allow_expand for n in tree.nodes() if len(n.data.path.relative_to(root).parts)>=2))
                self.assertTrue((core.STATE/'files-expanded.json').exists())
