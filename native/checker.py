import struct,re,hashlib,json,io
from pathlib import Path
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_INTR
from unicorn.arm_const import *
from .elfmap import map_elf
ENTRY=0x10100
from . import persistent as patcher
RAM="/tmp_bt/csboot-v1"

def padded(blob):return blob+b'\0\0' if len(blob)%512==0 else blob

def checker(address,before,after,any_data=False):
    n=len(before);size=32+2*n;stack=(size+8+7)&~7
    checks=''
    for offset,value in [(4,address),(8,n),(24,0)]+([(12,1),(16,n),(20,n),(28,0)] if after is not None else []):
        checks+=f' ldr r0,[r9,#{offset}]\n ldr r1,value_{offset}\n cmp r0,r1\n bne fail\n'
    constants=''.join(f'value_{offset}: .word {value}\n' for offset,value in [(4,address),(8,n),(24,0)]+([(12,1),(16,n),(20,n),(28,0)] if after is not None else []))
    compare=''
    if not any_data:
        compare+=' adr r0,expected\n add r1,r9,#32\n ldr r2,width\n bl compare\n cmp r0,#0\n bne fail\n'
    if after is not None:
        compare+=' adr r0,desired\n ldr r1,width\n add r1,r1,#32\n add r1,r9,r1\n ldr r2,width\n bl compare\n cmp r0,#0\n bne fail\n'
    src=f'''
 ldr r0,stack_size
 sub sp,sp,r0
 mov r9,sp
 adr r0,path
 mov r1,#0
 mov r2,#0
 mov r7,#5
 svc #0
 cmp r0,#0
 blt fail
 mov r8,r0
 mov r1,r9
 ldr r2,read_size
 mov r7,#3
 svc #0
 mov r10,r0
 mov r0,r8
 mov r7,#6
 svc #0
 cmp r0,#0
 bne fail
 ldr r0,frame_size
 cmp r10,r0
 bne fail
 ldr r0,[r9]
 cmp r0,#0
 blt fail
{checks}{compare}
 mov r0,#0
 b finish
fail:
 mov r0,#1
finish:
 mov r7,#1
 svc #0
compare:
 ldrb r3,[r0],#1
 ldrb r4,[r1],#1
 cmp r3,r4
 movne r0,#1
 bxne lr
 subs r2,r2,#1
 bne compare
 mov r0,#0
 bx lr
.balign 4
stack_size: .word {stack}
frame_size: .word {size}
read_size: .word {size+1}
width: .word {n}
{constants}
path: .asciz "{RAM}/last.bin"
.balign 4
expected: .byte {','.join(map(str,before))}
.balign 4
desired: .byte {','.join(map(str,after or before))}
'''
    return padded(patcher.assemble(src)),src

def verify_checker(blob,address,before,after,any_data=False):
    n=len(before)
    header=[3,address,n,1 if after is not None else 0,n if after is not None else 0,n if after is not None else 0,0,0]
    good=struct.pack('<8i',*header)+before+(after if after is not None else bytes(n))
    cases=[]
    for case in ('ok','missing','short','extra','bad-seek','bad-read','bad-close','changed-data','failed-write'):
        data=bytearray(good)
        if case=='short':data=data[:-1]
        if case=='extra':data+=b'x'
        if case=='bad-seek':struct.pack_into('<i',data,4,0)
        if case=='bad-read':struct.pack_into('<i',data,8,n-1)
        if case=='bad-close':struct.pack_into('<i',data,24,-1)
        if case=='changed-data':data[32]^=255
        if case=='failed-write':struct.pack_into('<i',data,16,-1)
        u=Uc(UC_ARCH_ARM,UC_MODE_ARM);map_elf(u,blob,0);u.mem_map(0x700000,0x20000,3);u.reg_write(UC_ARM_REG_SP,0x71ff00)
        exits=[]
        def syscall(u,_,__):
            nr=u.reg_read(UC_ARM_REG_R7);a,b,c=[u.reg_read(k) for k in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];ret=0
            if nr==5:
                assert bytes(u.mem_read(a,len(RAM+'/last.bin')+1))==(RAM+'/last.bin\0').encode() and b==0
                ret=-2 if case=='missing' else 3
            elif nr==3:assert a==3 and c==len(good)+1;u.mem_write(b,bytes(data));ret=len(data)
            elif nr==6:assert a==3
            elif nr==1:exits.append(a);u.emu_stop()
            else:raise AssertionError(nr)
            u.reg_write(UC_ARM_REG_R0,ret&0xffffffff)
        u.hook_add(UC_HOOK_INTR,syscall);u.emu_start(0x10100,0,count=20000)
        allowed=case=='ok' or (case=='changed-data' and any_data) or (case=='failed-write' and after is None)
        assert exits==[0 if allowed else 1],(case,exits)
        cases.append(dict(case=case,exit=exits[0]))
    return cases
