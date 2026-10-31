import struct,re,hashlib,json,io
from pathlib import Path
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_INTR
from unicorn.arm_const import *
from .elfmap import map_elf
ENTRY=0x10100
from .ram import build as ram_build
TARGET="/usr/bin/startBTCore.sh"
IDENTITY=dict(dev=64527,inode=39074,mode=33261,links=1,uid=57285,gid=1000,size=1283)

def assemble(src):
    code=bytes(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(src,addr=ENTRY)[0])
    blob=bytearray(256+len(code))
    blob[:52]=struct.pack('<16sHHIIIIIHHHHHH',b'\x7fELF\x01\x01\x01'+bytes(9),2,40,1,ENTRY,52,0,0x05000000,52,32,2,0,0,0)
    for i,p in enumerate([(1,0,0x10000,0x10000,len(blob),len(blob),5,4096),(0x6474e551,0,0,0,0,0,6,16)]):
        struct.pack_into('<8I',blob,52+32*i,*p)
    blob[256:]=code
    return bytes(blob)

def replace_once(source,old,new):
    assert source.count(old)==1, ('Unexpected verified core layout',old)
    return source.replace(old,new)

def build(before,after,offset,size,run_id,readonly=False):
    assert re.fullmatch('[0-9a-f]{32}',run_id)
    span=19 if offset==44 else 18 if offset==391 else None
    assert span and size in (1,span)
    assert before[:offset]==after[:offset] and before[offset+size:]==after[offset+size:]
    placeholder='/tmp_bt/csboot-patch-'+run_id+'/target.sh'
    _,src=ram_build(placeholder,before,after,offset,span)
    src=replace_once(src, f'target_path: .asciz "{placeholder}"', f'target_path: .asciz "{TARGET}"')
    src=replace_once(src,'tmpfs_magic: .word 0x01021994','tmpfs_magic: .word 0xef53')
    # Preserve the existing regular-file/length/link checks and add full identity.
    checks=''
    constants=''
    for label,at,value in [('device_lo',0,IDENTITY['dev']),('device_hi',4,0),
                            ('inode_lo',96,IDENTITY['inode']),('inode_hi',100,0),
                            ('mode',16,IDENTITY['mode']),('uid',24,IDENTITY['uid']),('gid',28,IDENTITY['gid'])]:
        checks+=f'    ldr r0, [r9, #{at}]\n    ldr r1, ident_{label}\n    cmp r0, r1\n    bne close\n'
        constants+=f'ident_{label}: .word {value}\n'
    src=replace_once(src,'    mov r10, #13\n',checks+'    mov r10, #13\n')
    if size!=span:
        src=replace_once(src,f'    mov r2, #{span}\n    mov r7, #4',f'    mov r2, #{size}\n    mov r7, #4')
        src=replace_once(src,f'    cmp r0, #{span}\n    bne close',f'    cmp r0, #{size}\n    bne close')
    gate='/tmp_bt/csboot-install-'+run_id+'/permit'
    token=('CSBOOT_PERSISTENT_MARKER_V1:'+run_id+'\n').encode()
    if readonly:
        src=replace_once(src,'    mov r1, #2\n','    mov r1, #0\n')
        start=src.index('    mov r10, #14\n')
        end=src.index('    mov r10, #0\nclose:',start)
        src=src[:start]+src[end:]
    else:
        gate_src=f'''
    mov r10, #20
    ldr r0, gate_ptr
    mov r1, #0
    mov r2, #0
    mov r7, #5
    svc #0
    cmp r0, #0
    blt finish
    mov r8,r0
    mov r1,r9
    mov r7,#100
    svc #0
    cmp r0,#0
    bne close
    ldr r0,[r9]
    ldr r1,gate_fs
    cmp r0,r1
    bne close
    mov r0,r8
    mov r1,r9
    mov r2,#{len(token)+1}
    mov r7,#3
    svc #0
    cmp r0,#{len(token)}
    bne close
    ldr r0,gate_token_ptr
    mov r1,r9
    mov r2,#{len(token)}
gate_loop:
    ldrb r3,[r0],#1
    ldrb r4,[r1],#1
    cmp r3,r4
    bne close
    subs r2,r2,#1
    bne gate_loop
    mov r0,r8
    mov r7,#6
    svc #0
    cmp r0,#0
    bne finish
    mov r8,#-1
'''
        src=replace_once(src,'    mov r10, #10\n',gate_src+'    mov r10, #10\n')
        constants+=f'gate_ptr: .word gate_path\ngate_token_ptr: .word gate_token\ngate_fs: .word 0x01021994\n'
        # The gate strings follow the fixed data; pointers avoid ADR range issues.
        src+=f'\n.balign 4\ngate_path: .asciz "{gate}"\ngate_token: .byte '+','.join(map(str,token))+'\n'
    src=replace_once(src,'path_ptr: .word target_path\n',constants+'path_ptr: .word target_path\n')
    return assemble(src),src,gate,token

def emulate(blob,before,after,offset,size,gate,token,scenario='ok',readonly=False):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);map_elf(u,blob,0)
    u.mem_map(0x700000,0x20000,3);u.reg_write(UC_ARM_REG_SP,0x71ff00)
    actual=before if scenario!='changed_preimage' else bytes([before[0]^255])+before[1:]
    initial=actual
    fds={};nextfd=3;writes=[];calls=[];exits=[];read_count=0
    def call(u,_,__):
        nonlocal actual,nextfd,read_count
        nr=u.reg_read(UC_ARM_REG_R7)
        a,b,c=[u.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
        calls.append(nr);ret=0
        if nr==5:
            name=bytes(u.mem_read(a,180)).split(b'\0')[0].decode()
            assert name in (TARGET,gate) and b==(0 if name==gate or readonly else 2)
            if name==gate and scenario=='gate_missing' or name==TARGET and scenario=='open_denied':ret=-30
            else:ret=nextfd;nextfd+=1;fds[ret]=dict(name=name,pos=0)
        elif nr==100:
            name=fds[a]['name'];magic=0x01021994 if name==gate else 0xef53
            if scenario=='wrong_fs' and name==TARGET or scenario=='gate_wrong_fs' and name==gate:magic=0
            u.mem_write(b,struct.pack('<I',magic)+bytes(60))
            if scenario=='statfs_failed':ret=-5
        elif nr==197:
            assert fds[a]['name']==TARGET
            stat=bytearray(104)
            for label,at,value,fmt in [('dev',0,64527,'Q'),('inode',96,39074,'Q'),('mode',16,33261,'I'),
                                      ('links',20,1,'I'),('uid',24,57285,'I'),('gid',28,1000,'I'),('size',48,1283,'Q')]:
                if scenario=='bad_'+label:value+=1
                struct.pack_into('<'+fmt,stat,at,value)
            u.mem_write(b,bytes(stat))
            if scenario=='stat_failed':ret=-5
        elif nr==19:
            assert fds[a]['name']==TARGET and b in (0,offset) and c==0
            fds[a]['pos']=b;ret=-5 if scenario=='seek_failed' else b
        elif nr==3:
            fd=fds[a]
            if fd['name']==gate:
                assert c==len(token)+1
                data=b'X'+token[1:] if scenario=='gate_wrong_token' else token
                ret=len(data);u.mem_write(b,data)
            else:
                assert c==1283;read_count+=1
                ret=-5 if scenario=='read_failed' or scenario=='reread_failed' and read_count>1 else 1282 if scenario=='short_read' else 1283
                if ret>0:
                    data=actual[fd['pos']:fd['pos']+ret]
                    if scenario=='reread_corrupt' and read_count>1:data=bytes([data[0]^255])+data[1:]
                    u.mem_write(b,data);fd['pos']+=ret
        elif nr==4:
            fd=fds[a]
            assert not readonly and fd['name']==TARGET and fd['pos']==offset and c==size and not writes
            data=bytes(u.mem_read(b,c));assert data==after[offset:offset+size]
            ret=-5 if scenario=='write_failed' else max(0,size-1) if scenario=='short_write' else size
            if ret>0:actual=actual[:offset]+data[:ret]+actual[offset+ret:]
            writes.append(dict(offset=offset,requested=c,result=ret))
        elif nr==118:
            assert not readonly and fds[a]['name']==TARGET
            if scenario=='sync_failed':ret=-5
        elif nr==6:
            fd=fds.pop(a)
            if scenario=='close_failed' and fd['name']==TARGET:ret=-5
        elif nr==1:exits.append(a);u.emu_stop()
        else:raise AssertionError(('Forbidden syscall',nr))
        u.reg_write(UC_ARM_REG_R0,ret&0xffffffff)
    u.hook_add(UC_HOOK_INTR,call);u.emu_start(ENTRY,0,count=60000)
    assert len(exits)==1 and (exits[0]==0)==(scenario=='ok'),(scenario,exits)
    assert len(actual)==1283 and actual[:offset]==initial[:offset] and actual[offset+size:]==initial[offset+size:]
    if scenario=='ok':assert actual==(before if readonly else after)
    if scenario not in ('ok','write_failed','short_write','sync_failed','reread_failed','reread_corrupt','close_failed'):
        assert not writes and actual==initial
    return dict(scenario=scenario,exitcode=exits[0],writes=writes,syscalls=calls,length_preserved=True,outside_edit_preserved=True)
