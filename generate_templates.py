"""Development only: assemble and fault-test immutable code + bounded data slots.

Assembler/emulator DLLs are NOT bundled with the end-user program. Runtime fills
only recorded data slots; tests compare filled artifacts byte-for-byte with fresh
assembly. No camera firmware or personal data is needed to generate these files.
"""
import hashlib,json
from pathlib import Path
from core import ASSETS
from native.memory import build as memory,verify as verify_memory
from native.checker import checker,verify_checker
from native.persistent import build as persistent,emulate
OUT=ASSETS/'templates';RUN='ab74c309d28e413bf65c709a18e2d305'
def pattern(n,seed):return bytes((i*17+seed)%256 for i in range(n))
def save(name,blob,src,values,cases):
    fields=[]
    for label,value in values.items():
        start=0
        while True:
            at=blob.find(value,start)
            if at<0:break
            fields.append(dict(name=label,offset=at,hex=value.hex()));start=at+len(value)
    occupied=set()
    for f in fields:
        span=set(range(f['offset'],f['offset']+len(bytes.fromhex(f['hex']))))
        assert not occupied&span;occupied|=span
    assert set(values)=={f['name'] for f in fields}
    (OUT/(name+'.bin')).write_bytes(blob);(OUT/(name+'.s')).write_text(src)
    return dict(sha256=hashlib.sha256(blob).hexdigest(),fields=fields,cases=len(cases))
def main():
    OUT.mkdir(exist_ok=True);meta={}
    for address,n in [(0x15779480,4),(0x15a08600,200),(0x15a08668,96)]:
        a=pattern(n,145);b=pattern(n,51)
        for writing in (False,True):
            aft=b if writing else None;blob,src=memory(158,address,a,aft)
            vals={'before':a,**({'after':b} if writing else {})}
            name=f'mem-{address:x}-{n}-{int(writing)}';meta[name]=save(name,blob,src,vals,verify_memory(blob,158,address,a,aft))
            if n==200:
                blob,src=checker(address,a,aft);name=f'check-{int(writing)}';meta[name]=save(name,blob,src,vals,verify_checker(blob,address,a,aft))
    faults=('ok','gate_missing','gate_wrong_token','gate_wrong_fs','open_denied','wrong_fs','statfs_failed','stat_failed','bad_dev','bad_inode','bad_mode','bad_links','bad_uid','bad_gid','bad_size','changed_preimage','seek_failed','read_failed','short_read','write_failed','short_write','sync_failed','reread_failed','reread_corrupt','close_failed')
    for at,n,readonly in [(44,1,False),(44,19,False),(391,1,False),(391,18,False),(44,1,True)]:
        a=pattern(1283,145);b=a[:at]+bytes([51])*n+a[at+n:]
        blob,src,gate,token=persistent(a,b,at,n,RUN,readonly)
        scenarios=('ok',) if readonly else faults
        cases=[emulate(blob,a,b,at,n,gate,token,s,readonly) for s in scenarios]
        vals={'before':a,'after':b,**({} if readonly else {'run':RUN.encode()})}
        meta[f'persist-{at}-{n}-{int(readonly)}']=save(f'persist-{at}-{n}-{int(readonly)}',blob,src,vals,cases)
    (OUT/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(dict(templates=len(meta),fault_cases=sum(v['cases'] for v in meta.values()),camera_accessed=False)))
if __name__=='__main__':main()
