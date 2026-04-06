import base64
from typing import Any
from importlib import import_module

def relativize_module(mod:str,name):
    if mod == name:
        return {'type':'relative', 'path':[]}
    elif mod.startswith(name):
        return {'type':'relative', 'path':mod[len(name):].lstrip('.').split('.')} # will be non-empty
    else:
        return {'type':'absolute','path':mod.split('.')}

def derelativize_module(mod,name:str):
    if mod['type'] == 'relative':
        prefix = [] if name == '__main__' else  name.split('.')
        return '.'.join(prefix + mod['path'])
    else:
        return '.'.join(mod['path'])


def serialize(obj,name:str):
    if type(obj) in [int,str,float]:
        return obj
    elif type(obj) == bytes:
        return {
            "type" : "bytes",
            "contents": base64.b64encode(obj).decode("utf-8")
        }
    elif type(obj) in [list,tuple]:
        return {
            "type" : type(obj).__name__,
            "contents" : [serialize(child,name) for child in obj]
        }
    elif type(obj) == dict: # JSON dicts must have string keys, so instead we do this as list of tuples
        return {
            "type" : "dict",
            "contents" : [[serialize(k,name), serialize(v,name)] for k,v in obj.items()]
        }
    elif hasattr(obj, "__dict__") and hasattr(obj, "__class__"): # is a member of a normal Python class
        return {
            "type" : "obj",
            "module" : relativize_module(obj.__class__.__module__,name),
            "class" : obj.__class__.__qualname__,
            "contents": {k : serialize(v,name)  for k,v in obj.__dict__.items()}
        }

def deserialize(json,name:str,globals):
    if type(json) in [int,str,float,type(None)]:
        return json
    elif json['type'] == 'bytes':
        return base64.b64decode(json['contents'])
    elif json['type'] in ['list','tuple']:
        return __builtins__[json['type']](deserialize(child,name,globals) for child in json['contents'])
    elif json['type'] == 'dict':
        return dict((deserialize(k,name,globals), deserialize(v,name,globals)) for k,v in json['contents'])
    elif json['type'] == 'obj':
        modname = derelativize_module(json['module'],name)
        namespace = globals if modname == '' else import_module(modname).__dict__
        cls = namespace[json['class']]
        def empty_init(a):
            pass
        old_init = cls.__init__
        cls.__init__ = empty_init
        obj = cls()
        cls.__init__ = old_init
        for k,v in json['contents'].items():
            setattr(obj, k,deserialize(v,name,globals))
        return obj
