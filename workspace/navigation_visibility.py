"""Local sidebar-only visibility rules, independent of discovered project IDs."""
import json
import core


def identity(project):
    if project.get('kind')=='tmux-live' and project.get('source_socket') and project.get('source_session'):
        return json.dumps(['tmux',project['source_socket'],project['source_session']],ensure_ascii=False)
    return json.dumps(['project',project['id']],ensure_ascii=False)


def rules():
    try: value=json.loads((core.STATE/'navigation-hidden.json').read_text())
    except (OSError,ValueError): return {}
    return value if isinstance(value,dict) else {}


def hidden(project,saved=None):
    return identity(project) in (rules() if saved is None else saved)


def hide(project):
    key=identity(project)
    def update(saved):
        saved[key]={'name':project['name'],'session':project.get('source_session',''),'socket':project.get('source_socket','')}
    core.locked_update(core.STATE/'navigation-hidden.json',update)


def restore(key):
    def update(saved): saved.pop(key,None)
    core.locked_update(core.STATE/'navigation-hidden.json',update)
