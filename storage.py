import json,os
from pathlib import Path
def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp')
    with temp.open('w',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
def read_json(path,default=None):
    p=Path(path);return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
