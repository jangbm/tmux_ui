"""Bounded lazy Files tree with per-root expansion state in ignored local data."""
import asyncio
import json
from itertools import islice
from pathlib import Path
from textual.widgets import DirectoryTree
from textual import work
import core

class ProjectFiles(DirectoryTree):
    ICON_NODE=''
    ICON_NODE_EXPANDED=''
    ICON_FILE=''
    SKIP={'.git','.venv','venv','node_modules','__pycache__','Library','Temp','obj'}
    MAX_DEPTH=8
    MAX_ENTRIES=200
    MAX_NODES=1000
    BULK_DEPTH=3
    BULK_FOLDERS=40
    def __init__(self,*args,**kwargs):
        self.saved_root=None;self.restoring=True;self.limited=False;self.generation=0
        super().__init__(*args,**kwargs)
    def filter_paths(self,paths):
        entries=list(islice(paths,self.MAX_ENTRIES+1))
        if len(entries)>self.MAX_ENTRIES: self.limited=True
        return [p for p in entries[:self.MAX_ENTRIES] if p.name not in self.SKIP and not p.is_symlink()]
    def nodes(self):
        pending=[self.root]
        while pending:
            node=pending.pop();yield node;pending.extend(reversed(node.children))
    def _populate_node(self,node,content):
        remaining=max(0,self.MAX_NODES-sum(1 for n in self.nodes())+len(node.children))
        content=[path for path in content if path.is_relative_to(Path(self.path))]
        if len(content)>remaining: self.limited=True
        super()._populate_node(node,content[:remaining])
        for child in node.children:
            if child.data and len(child.data.path.relative_to(Path(self.path)).parts)>=self.MAX_DEPTH:
                child.allow_expand=False;self.limited=True
        self.tooltip='최대 깊이 8 · 항목 1000 · 폴더당 200 (일부 항목 생략)' if self.limited else '펼치기: 선택 폴더부터 3단계 · 최대 40폴더'
    def save_open(self):
        if self.restoring or self.saved_root is None: return
        paths=[str(n.data.path.relative_to(Path(self.saved_root))) for n in self.nodes() if n.data and n.data.path.is_relative_to(Path(self.saved_root)) and n.allow_expand and n.is_expanded][:self.MAX_NODES]
        root=self.saved_root
        def update(data):
            data[root]=paths
            while len(data)>100: del data[next(iter(data))]
        core.locked_update(core.STATE/'files-expanded.json',update)
    async def watch_path(self):
        self.save_open();self.restoring=True;self.generation+=1;self.limited=False
        self.saved_root=str(self.path)
        try:
            saved=json.loads((core.STATE/'files-expanded.json').read_text()).get(self.saved_root,None)
        except (OSError,ValueError,AttributeError): saved=None
        if not isinstance(saved,list): saved=None
        generation=self.generation
        await super().watch_path()
        if generation!=self.generation: return
        wanted={item for item in (saved or [])[:self.MAX_NODES] if isinstance(item,str)};pending=[self.root];count=0
        while pending and count<self.MAX_NODES:
            node=pending.pop(0);count+=1
            if node.data and node.allow_expand and str(node.data.path.relative_to(Path(self.path))) in wanted:
                node.expand();await self._add_to_load_queue(node);pending.extend(node.children)
        if saved is not None and '.' not in wanted: self.root.collapse()
        self.restoring=False
    async def _on_tree_node_expanded(self,event):
        await super()._on_tree_node_expanded(event)
        if not self.restoring: self.save_open()
    def on_tree_node_collapsed(self,event):
        if not self.restoring: self.save_open()
    def on_unmount(self): self.save_open()
    @work(exclusive=True,group='file-expand')
    async def expand_levels(self):
        generation=self.generation
        start=self.cursor_node or self.root
        if not start.allow_expand: start=start.parent or self.root
        pending=[(start,0)];count=0
        while pending and count<self.BULK_FOLDERS and generation==self.generation:
            node,depth=pending.pop(0)
            if not node.allow_expand or depth>=self.BULK_DEPTH: continue
            node.expand();await self._add_to_load_queue(node);count+=1
            if sum(1 for n in self.nodes())>=self.MAX_NODES: self.limited=True;break
            pending.extend((child,depth+1) for child in node.children if child.allow_expand)
            await asyncio.sleep(0)
        if generation==self.generation:
            self.save_open()
            self.app.notify(f'{count}개 폴더 펼침 · 최대 3단계/40폴더'+(' · 일부 항목 생략' if self.limited or pending else ''),timeout=3)
    @work(exclusive=True,group='file-collapse')
    async def collapse_levels(self):
        self.workers.cancel_group(self,'file-expand');self.generation+=1
        await self._load_queue.join()
        start=self.cursor_node or self.root
        if not start.allow_expand: start=start.parent or self.root
        pending=[start]
        while pending:
            node=pending.pop();pending.extend(node.children);node.collapse()
        self.save_open()
