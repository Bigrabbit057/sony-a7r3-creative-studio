import io
from elftools.elf.elffile import ELFFile

def map_elf(uc, blob, base):
    elf=ELFFile(io.BytesIO(blob))
    for seg in elf.iter_segments():
        if seg['p_type']!='PT_LOAD': continue
        low=seg['p_vaddr']&~4095
        high=(seg['p_vaddr']+seg['p_memsz']+4095)&~4095
        flags=seg['p_flags'];perms=(1 if flags&4 else 0)|(2 if flags&2 else 0)|(4 if flags&1 else 0)
        uc.mem_map(base+low, high-low, perms)
        uc.mem_write(base+seg['p_vaddr'],seg.data())
    return elf
