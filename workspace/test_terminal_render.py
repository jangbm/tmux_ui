import unittest
from terminal_render import chat_terminal_text

class TerminalRenderingTests(unittest.TestCase):
    def test_background_and_reverse_are_removed_but_text_color_and_dim_survive(self):
        screen='\x1b[49m기본\x1b[48;5;231m흰 배경\x1b[7m반전\x1b[0m\x1b[2;38;5;246m추천\x1b[0m'
        text=chat_terminal_text(screen)
        self.assertEqual(text.plain,'기본흰 배경반전추천')
        self.assertTrue(all(span.style.bgcolor is None and not span.style.reverse for span in text.spans))
        suggestion=next(span for span in text.spans if span.style.dim)
        self.assertEqual(suggestion.style.color.number,246)
    def test_terminal_default_foreground_uses_chat_theme(self):
        text=chat_terminal_text('\x1b[39;49m답변\x1b[0m')
        self.assertTrue(all(s.style.color is None and s.style.bgcolor is None for s in text.spans))

    def test_user_interface_keeps_requested_colors_even_with_no_color_environment(self):
        import os,runpy,tempfile
        from pathlib import Path
        from unittest.mock import patch
        import core
        Sidebar=runpy.run_path(str(core.ROOT/'sidebar.py'))['Sidebar']
        Desktop=runpy.run_path(str(core.ROOT/'desktop-app.py'))['Desktop']
        with patch.dict(os.environ,{'NO_COLOR':'1'}):
            self.assertFalse(Sidebar().no_color)
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'STATE',Path(tmp)),patch.dict(os.environ,{'NO_COLOR':'1'}):
            self.assertFalse(Desktop({'id':'test'},publish=False).no_color)

    def test_result_stays_red_when_sidebar_row_is_selected(self):
        import runpy
        import core
        from rich.text import Text
        from rich.style import Style
        from rich.console import Console
        ProjectTree=runpy.run_path(str(core.ROOT/'sidebar.py'))['ProjectTree']
        tree=ProjectTree('projects');node=tree.root.add(Text('stock  결과'))
        label=tree.render_label(node,Style(),Style(color='white',bgcolor='#2b3741'))
        self.assertEqual(label.get_style_at_offset(Console(),label.plain.index('결과')).color.name,'#f08080')

    def test_prompt_rules_do_not_wrap_but_text_and_tables_remain(self):
        source='답변\n'+'─'*160+'\n❯ \x1b[2m추천 문구\x1b[22m\n'+'─'*100+' branch-name ─\n  auto mode on\n┌────┬────┐\n│ A  │ B  │'
        text=chat_terminal_text(source)
        self.assertEqual(text.plain,'답변\n❯ 추천 문구\nbranch-name\n  auto mode on\n┌────┬────┐\n│ A  │ B  │')
        self.assertTrue(any(span.style.dim for span in text.spans))
