"""Grouped tabs, independent composers and latest-message navigation."""
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
import core
from desk_state import DeskState

module=runpy.run_path(str(core.ROOT/'desktop-app.py'))
Desktop=module['Desktop']; ProjectView=module['ProjectView']; ChatPanel=module['ChatPanel']; TabChip=module['TabChip']; TabLabel=module['TabLabel']


class GroupStateTests(unittest.TestCase):
    def test_drag_moves_identity_and_closing_empty_group_collapses_it(self):
        state=DeskState(); first=state.open('claude-project'); second=state.open('both-project')
        state.split(second['id'],'right')
        self.assertEqual(len(state.groups),2)
        self.assertEqual(state.group()['tabs'][0]['id'],second['id'])
        state.move(second['id'],state.groups[0]['id'],first['id'])
        self.assertEqual(len(state.groups),1)
        self.assertEqual(state.groups[0]['tabs'][0]['id'],second['id'])
        state.split(second['id'],'below',copy=True)
        self.assertEqual(state.value['axis'],'below')
        self.assertEqual(len(state.groups),2)


class DesktopTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        for name,value in [('CONFIG',self.root/'projects.json'),('STATE',self.root/'state')]:
            item=patch.object(core,name,value); item.start(); self.addCleanup(item.stop)
        self.owner=core.add('Workspace',self.root/'owner',claude=False,codex=False)
        self.one=core.add('unity',self.root/'one',codex=False)
        self.two=core.add('control',self.root/'two')
    async def test_grouped_headers_panel_counts_close_and_drafts_survive_move(self):
        state=DeskState(); one=state.open(self.one['id']); two=state.open(self.two['id'])
        app=Desktop(self.owner,state.value,publish=False)
        async with app.run_test(size=(160,45)) as pilot:
            await pilot.pause()
            view=app.views[two['id']]
            self.assertEqual(len(view.panels),2)
            view.panels['claude'].query_one('.composer').insert('keep this draft')
            app.split_tab(two['id'],'right')
            await pilot.pause()
            self.assertEqual(len(app.groups),2)
            self.assertEqual(len(list(app.query('.group-tabs'))),2)
            self.assertIs(app.views[two['id']],view)
            self.assertEqual(view.panels['claude'].query_one('.composer').text,'keep this draft')
            self.assertEqual(len(app.views[one['id']].panels),1)
            await pilot.click(view.panels['codex'].query_one('.close-chat'))
            await pilot.pause()
            self.assertFalse(view.panels['codex'].display)
            app.show_chat(two['id'],'codex')
            self.assertTrue(view.panels['codex'].display)
            app.state.move(two['id'],app.state.groups[0]['id']); app.render_state()
            await pilot.pause()
            self.assertEqual(len(app.groups),1)
            self.assertIs(app.views[two['id']],view)
            app.close_tab(two['id']); app.open_project(self.two['id'])
            await pilot.pause()
            self.assertIs(app.views[two['id']],view)
    async def test_mouse_drag_to_content_edge_creates_independent_tab_group(self):
        state=DeskState(); one=state.open(self.one['id']); state.open(self.two['id'])
        app=Desktop(self.owner,state.value,publish=False)
        async with app.run_test(size=(150,40)) as pilot:
            await pilot.pause()
            label=next(t for t in app.query(TabChip) if t.tab_id==one['id']).query_one(TabLabel)
            view=app.views[one['id']]
            await pilot.mouse_down(label,offset=(2,0))
            await pilot.hover('#stage',offset=(145,20))
            self.assertTrue(app.query_one('#drop-preview').display)
            await pilot.mouse_up('#stage',offset=(145,20))
            await pilot.pause()
            self.assertEqual(len(app.groups),2)
            self.assertIs(app.views[one['id']],view)
            label=next(t for t in app.query(TabChip) if t.tab_id==one['id']).query_one(TabLabel)
            await pilot.mouse_down(label,offset=(2,0))
            await pilot.hover('#stage',offset=(5,1))
            await pilot.mouse_up('#stage',offset=(5,1))
            await pilot.pause()
            self.assertEqual(len(app.groups),1)
            self.assertIs(app.views[one['id']],view)

    async def test_tab_activation_shows_latest_message(self):
        messages=[{'role':'assistant','text':f'line {i}\n'+'long message\n'*4} for i in range(40)]
        core.atomic(core.STATE/'chats'/f"{self.one['id']}-claude.json",{'session':None,'messages':messages})
        state=DeskState(); one=state.open(self.one['id']); two=state.open(self.two['id'])
        app=Desktop(self.owner,state.value,publish=False)
        async with app.run_test(size=(120,32)) as pilot:
            await pilot.pause()
            app.select_tab(one['id']); await pilot.pause()
            thread=app.views[one['id']].panels['claude'].query_one('.thread')
            self.assertGreater(thread.max_scroll_y,0)
            self.assertEqual(thread.scroll_y,thread.max_scroll_y)
            thread.scroll_home(animate=False); await pilot.pause()
            app.select_tab(two['id']); await pilot.pause()
            app.select_tab(one['id']); await pilot.pause()
            self.assertEqual(thread.scroll_y,thread.max_scroll_y)
