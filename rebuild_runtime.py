"""Offline reproducibility check for the shipped ARM programs and title hook."""
import hashlib,json,struct,sys
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM,KS_MODE_THUMB
from core import ASSETS
from native.persistent import assemble
from payload import padded

def main():
    results=[]
    for source in sorted((ASSETS/'runtime').glob('*.s')):
        expected=source.with_suffix('.elf').read_bytes()
        actual=padded(assemble(source.read_text()))
        assert actual==expected,source.name
        results.append(source.name)
    hook=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm((ASSETS/'hook.S').read_text(),addr=0x832600)[0])
    assert hook==(ASSETS/'hook.bin').read_bytes(),'title hook differs'
    entry=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm('b.w #0x832600',addr=0x5a3480)[0])
    assert entry==(ASSETS/'entry.bin').read_bytes(),'title branch differs'
    sys.path.insert(0,str(ASSETS))
    from creative_autostart_runtime import learner,COMMON
    assert learner()==(ASSETS/'runtime/learner.sh').read_bytes(),'learner generator differs'
    assert COMMON.encode()==(ASSETS/'runtime/common.sh').read_bytes(),'record helper differs'
    print(json.dumps(dict(ok=True,arm_programs=len(results),hook_bytes=len(hook),learner_reproduced=True,camera_accessed=False)))
if __name__=='__main__':main()
