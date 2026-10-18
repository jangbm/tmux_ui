"""Editor-group state: moving a tab keeps its identity, chat and draft alive."""
from copy import deepcopy
from uuid import uuid4


def identity(): return 't'+uuid4().hex[:10]


class DeskState:
    def __init__(self,value=None):
        self.value=deepcopy(value) if value else {'version':1,'axis':'right','ratio':.5,'active_group':'g1',
            'groups':[{'id':'g1','tabs':[],'active':None}]}
    @property
    def groups(self): return self.value['groups']
    def group(self,key=None):
        key=key or self.value['active_group']
        return next((g for g in self.groups if g['id']==key),self.groups[0])
    def locate(self,tab_id):
        for group in self.groups:
            for tab in group['tabs']:
                if tab['id']==tab_id: return group,tab
        raise ValueError('열린 탭을 찾을 수 없습니다')
    def open(self,project,group=None):
        group=self.group(group)
        tab=next((t for t in group['tabs'] if t['project']==project),None)
        if not tab:
            tab={'id':identity(),'project':project,'hidden':[]}; group['tabs'].append(tab)
        self.select(tab['id']); return tab
    def select(self,tab_id):
        group,tab=self.locate(tab_id)
        group['active']=tab_id; self.value['active_group']=group['id']
        return tab
    def move(self,tab_id,target_group,before=None,after=False):
        source,tab=self.locate(tab_id); target=self.group(target_group)
        if before==tab_id: return
        source['tabs'].remove(tab)
        index=next((i for i,t in enumerate(target['tabs']) if t['id']==before),len(target['tabs']))
        if before: index+=int(after)
        target['tabs'].insert(index,tab)
        if source['active']==tab_id: source['active']=source['tabs'][min(index,len(source['tabs'])-1)]['id'] if source['tabs'] else None
        if source is not target and not source['tabs'] and len(self.groups)>1: self.groups.remove(source)
        self.select(tab_id)
    def split(self,tab_id,direction='right',copy=False):
        source,tab=self.locate(tab_id)
        if direction not in ('left','right','above','below'): raise ValueError('Unknown split')
        if len(self.groups)>=2:
            target=next(g for g in self.groups if g is not source)
            if not copy: self.move(tab_id,target['id']); return tab
            return self.open(tab['project'],target['id'])
        target={'id':'g'+uuid4().hex[:6],'tabs':[],'active':None}
        self.value['axis']='right' if direction in ('left','right') else 'below'
        self.groups.insert(0 if direction in ('left','above') else len(self.groups),target)
        if copy: return self.open(tab['project'],target['id'])
        if len(source['tabs'])==1:
            # Dragging the sole tab creates a second view, never an empty split.
            return self.open(tab['project'],target['id'])
        self.move(tab_id,target['id']); return tab
    def close(self,tab_id):
        group,tab=self.locate(tab_id)
        group['tabs'].remove(tab)
        if group['active']==tab_id: group['active']=group['tabs'][-1]['id'] if group['tabs'] else None
        if not group['tabs'] and len(self.groups)>1: self.groups.remove(group)
        self.value['active_group']=self.groups[0]['id'] if group not in self.groups else group['id']
        return tab
