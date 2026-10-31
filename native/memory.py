import struct,re,hashlib,json,io
from pathlib import Path
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_INTR
from unicorn.arm_const import *
from .elfmap import map_elf
ENTRY=0x10100

def build(pid,address,before,after=None):
    n=len(before);assert 1<=n<=512 and (after is None or len(after)==n)
    assert 1<pid<65536 and 0x10000<=address<0x70000000 and (address&4095)+n<=4096
    total=(32+2*n+7)&~7
    src=f'''
    ldr r0,frame_size
    sub sp,sp,r0
    mov r9,sp
    mov r1,#0
    mov r2,#0
zero:
    str r1,[r9,r2]
    add r2,r2,#4
    cmp r2,r0
    blo zero
    adr r0,path
    mov r1,#{2 if after is not None else 0}
    mov r2,#0
    mov r7,#5
    svc #0
    str r0,[r9]
    cmp r0,#0
    blt report
    mov r8,r0
    bl seek
    str r0,[r9,#4]
    cmp r0,#0
    blt close
    mov r0,r8
    add r1,r9,#32
    ldr r2,size
    mov r7,#3
    svc #0
    str r0,[r9,#8]
    ldr r2,size
    cmp r0,r2
    bne close
'''
    if after is not None:
        src+='''
    adr r0,expected
    add r1,r9,#32
compare:
    ldrb r3,[r0],#1
    ldrb r4,[r1],#1
    cmp r3,r4
    bne close
    subs r2,r2,#1
    bne compare
    mov r0,#1
    str r0,[r9,#12]
    bl seek
    cmp r0,#0
    blt close
    mov r0,r8
    adr r1,desired
    ldr r2,size
    mov r7,#4
    svc #0
    str r0,[r9,#16]
    ldr r2,size
    cmp r0,r2
    beq reread
    bl seek
    cmp r0,#0
    blt close
    mov r0,r8
    add r1,r9,#32
    ldr r2,size
    mov r7,#4
    svc #0
    str r0,[r9,#28]
reread:
    bl seek
    cmp r0,#0
    blt close
    mov r0,r8
    ldr r1,size
    add r1,r1,#32
    add r1,r9,r1
    ldr r2,size
    mov r7,#3
    svc #0
    str r0,[r9,#20]
'''
    src+=f'''
close:
    mov r0,r8
    mov r7,#6
    svc #0
    str r0,[r9,#24]
report:
    mov r0,#1
    mov r1,r9
    ldr r2,report_size
    mov r7,#4
    svc #0
    ldr r2,report_size
    cmp r0,r2
    moveq r0,#0
    movne r0,#1
    mov r7,#1
    svc #0
seek:
    mov r0,r8
    ldr r1,address
    mov r2,#0
    mov r7,#19
    svc #0
    bx lr
.balign 4
size: .word {n}
frame_size: .word {total}
report_size: .word {32+2*n}
address: .word {address}
path: .asciz "/proc/{pid}/mem"
.balign 4
expected: .byte {','.join(map(str,before))}
.balign 4
desired: .byte {','.join(map(str,after if after is not None else before))}
'''
    code=bytes(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(src,addr=ENTRY)[0]);blob=bytearray(0x100+len(code))
    blob[:52]=struct.pack('<16sHHIIIIIHHHHHH',b'\x7fELF\x01\x01\x01'+bytes(9),2,40,1,ENTRY,52,0,0x05000000,52,32,2,0,0,0)
    for i,p in enumerate([(1,0,0x10000,0x10000,len(blob),len(blob),5,4096),(0x6474e551,0,0,0,0,0,6,16)]):struct.pack_into('<8I',blob,52+32*i,*p)
    blob[0x100:]=code;return bytes(blob),src

def verify(blob,pid,address,before,after):
    cases=[];n=len(before)
    for scenario in ('ok','open_denied','seek_failed','read_denied','short_read','changed_bytes','write_failed','short_write','reread_failed'):
        u=Uc(UC_ARCH_ARM,UC_MODE_ARM);map_elf(u,blob,0);u.mem_map(0x700000,0x20000,3);u.reg_write(UC_ARM_REG_SP,0x71ff00)
        memory=bytes([before[0]^255])+before[1:] if scenario=='changed_bytes' else before
        calls=[];out=[];exits=[];reads=[];writes=[]
        def syscall(u,_,__):
            nonlocal memory
            nr=u.reg_read(UC_ARM_REG_R7);a,b,c=[u.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];calls.append(nr);ret=0
            if nr==5:
                assert bytes(u.mem_read(a,len(f'/proc/{pid}/mem')+1))==f'/proc/{pid}/mem\0'.encode() and b==(2 if after is not None else 0)
                ret=-13 if scenario=='open_denied' else 3
            elif nr==19:assert (a,b,c)==(3,address,0);ret=-22 if scenario=='seek_failed' else address
            elif nr==3:
                assert a==3 and c==n;reads.append(1)
                ret=-5 if scenario=='read_denied' or (scenario=='reread_failed' and len(reads)>1) else (n-1 if scenario=='short_read' else n)
                if ret>0:u.mem_write(b,memory[:ret])
            elif nr==4:
                if a==3:
                    raw=bytes(u.mem_read(b,c));assert after is not None and c==n and raw==(after if not writes else before);writes.append(raw)
                    ret=-5 if scenario=='write_failed' else (n-1 if scenario=='short_write' and len(writes)==1 else n)
                    if ret>0:memory=raw[:ret]+memory[ret:]
                else:assert a==1 and c==32+2*n;out.append(bytes(u.mem_read(b,c)));ret=c
            elif nr==6:assert a==3
            elif nr==1:exits.append(a);u.emu_stop()
            else:raise AssertionError(nr)
            u.reg_write(UC_ARM_REG_R0,ret&0xffffffff)
        u.hook_add(UC_HOOK_INTR,syscall);u.emu_start(ENTRY,0,count=20000)
        assert exits==[0] and len(out)==1
        if after is None or scenario in ('open_denied','seek_failed','read_denied','short_read','changed_bytes'):assert not writes
        if scenario in ('write_failed','short_write'):assert memory==before
        if scenario=='ok' and after is not None:assert memory==after and out[0][32+n:32+2*n]==after
        cases.append(dict(scenario=scenario,syscalls=calls,results=list(struct.unpack('<8i',out[0][:32]))))
    return cases
