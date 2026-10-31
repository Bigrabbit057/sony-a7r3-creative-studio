"""Fill preverified data fields without an assembler or emulator at runtime."""
import hashlib,re
from core import ASSETS,load
def fill(name,values):
    meta=load(ASSETS/'templates/manifest.json')[name];blob=(ASSETS/'templates'/(name+'.bin')).read_bytes();src=(ASSETS/'templates'/(name+'.s')).read_text()
    if hashlib.sha256(blob).hexdigest()!=meta['sha256']:raise ValueError('原生模板校验失败')
    if set(values)!={f['name'] for f in meta['fields']}:raise ValueError('模板字段不匹配')
    out=bytearray(blob);allowed=set();text_replacements={}
    for f in meta['fields']:
        old=bytes.fromhex(f['hex']);new=values[f['name']];at=f['offset']
        if len(old)!=len(new) or blob[at:at+len(old)]!=old:raise ValueError('模板数据边界不符')
        allowed.update(range(at,at+len(old)));out[at:at+len(old)]=new
        if f['name']=='run':text_replacements[old.decode()]=new.decode()
        text_replacements[','.join(map(str,old))]=','.join(map(str,new))
    if any(i not in allowed for i,(a,b) in enumerate(zip(blob,out)) if a!=b):raise ValueError('修改超出模板数据区')
    # Simultaneous replacements avoid newly inserted data being mistaken for a
    # second placeholder (e.g. the before/after program differ by one byte).
    src=re.sub('|'.join(re.escape(k) for k in sorted(text_replacements,key=len,reverse=True)),lambda m:text_replacements[m[0]],src)
    return bytes(out),src
