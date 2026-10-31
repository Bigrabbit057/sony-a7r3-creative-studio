import struct,re,hashlib,json,io
from pathlib import Path
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_INTR
from unicorn.arm_const import *
from .elfmap import map_elf
ENTRY=0x10100

def build(target, before, after, offset, size):
    assert re.fullmatch(r'/tmp_bt/csboot-patch-[0-9a-f]{32}/target.sh', target)
    assert len(before) == len(after) == 1283
    assert (offset, size) in ((44, 19), (391, 18))
    assert before[:offset] == after[:offset] and before[offset+size:] == after[offset+size:]
    assert before != after
    src = f'''
    sub sp, sp, #2048
    mov r9, sp
    mov r8, #-1
    mov r10, #10
    ldr r0, path_ptr
    mov r1, #2
    mov r2, #0
    mov r7, #5
    svc #0
    cmp r0, #0
    blt finish
    mov r8, r0
    mov r10, #11
    mov r1, r9
    mov r7, #100
    svc #0
    cmp r0, #0
    bne close
    ldr r0, [r9]
    ldr r1, tmpfs_magic
    cmp r0, r1
    bne close
    mov r10, #12
    mov r0, r8
    mov r1, r9
    mov r7, #197
    svc #0
    cmp r0, #0
    bne close
    ldr r0, [r9, #16]
    and r0, r0, #0xf000
    cmp r0, #0x8000
    bne close
    ldr r0, [r9, #20]
    cmp r0, #1
    bne close
    ldr r0, [r9, #48]
    ldr r1, file_size
    cmp r0, r1
    bne close
    ldr r0, [r9, #52]
    cmp r0, #0
    bne close
    mov r10, #13
    bl read_all
    cmp r0, #0
    bne close
    ldr r1, before_ptr
    bl compare
    cmp r0, #0
    bne close
    mov r10, #14
    mov r0, r8
    ldr r1, patch_offset
    mov r2, #0
    mov r7, #19
    svc #0
    ldr r1, patch_offset
    cmp r0, r1
    bne close
    mov r10, #15
    mov r0, r8
    ldr r1, after_ptr
    ldr r2, patch_offset
    add r1, r1, r2
    mov r2, #{size}
    mov r7, #4
    svc #0
    cmp r0, #{size}
    bne close
    mov r10, #16
    mov r0, r8
    mov r7, #118
    svc #0
    cmp r0, #0
    bne close
    mov r10, #17
    bl read_all
    cmp r0, #0
    bne close
    ldr r1, after_ptr
    bl compare
    cmp r0, #0
    bne close
    mov r10, #0
close:
    mov r0, r8
    mov r7, #6
    svc #0
    cmp r0, #0
    movne r10, #18
finish:
    mov r0, r10
    mov r7, #1
    svc #0
    b finish
read_all:
    push {{lr}}
    mov r0, r8
    mov r1, #0
    mov r2, #0
    mov r7, #19
    svc #0
    cmp r0, #0
    bne read_bad
    mov r0, r8
    mov r1, r9
    ldr r2, file_size
    mov r7, #3
    svc #0
    ldr r1, file_size
    cmp r0, r1
    bne read_bad
    mov r0, #0
    pop {{pc}}
read_bad:
    mov r0, #1
    pop {{pc}}
compare:
    mov r0, r9
    ldr r2, file_size
compare_loop:
    ldrb r3, [r0], #1
    ldrb r4, [r1], #1
    cmp r3, r4
    bne compare_bad
    subs r2, r2, #1
    bne compare_loop
    mov r0, #0
    bx lr
compare_bad:
    mov r0, #1
    bx lr
.balign 4
tmpfs_magic: .word 0x01021994
file_size: .word 1283
patch_offset: .word {offset}
path_ptr: .word target_path
before_ptr: .word expected_before
after_ptr: .word expected_after
target_path: .asciz "{target}"
.balign 4
expected_before: .byte {','.join(map(str,before))}
.balign 4
expected_after: .byte {','.join(map(str,after))}
'''
    code = bytes(Ks(KS_ARCH_ARM, KS_MODE_ARM).asm(src, addr=ENTRY)[0])
    blob = bytearray(0x100 + len(code))
    blob[:52] = struct.pack('<16sHHIIIIIHHHHHH', b'\x7fELF\x01\x01\x01'+bytes(9), 2, 40, 1, ENTRY, 52, 0, 0x05000000, 52, 32, 2, 0, 0, 0)
    for i, p in enumerate([(1, 0, 0x10000, 0x10000, len(blob), len(blob), 5, 4096), (0x6474e551, 0, 0, 0, 0, 0, 6, 16)]):
        struct.pack_into('<8I', blob, 52+32*i, *p)
    blob[0x100:] = code
    return bytes(blob), src

def verify(blob, target, before, after, offset, size):
    rows = []
    scenarios = ('ok', 'open_denied', 'wrong_fs', 'statfs_failed', 'stat_failed', 'not_regular', 'hardlinked',
                 'wrong_size', 'changed_preimage', 'seek_failed', 'read_failed', 'short_read',
                 'write_failed', 'short_write', 'sync_failed', 'reread_failed', 'reread_corrupt', 'close_failed')
    for scenario in scenarios:
        u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        map_elf(u, blob, 0)
        u.mem_map(0x700000, 0x20000, 3)
        u.reg_write(UC_ARM_REG_SP, 0x71ff00)
        actual = before if scenario != 'changed_preimage' else bytes([before[0]^255]) + before[1:]
        initial = actual
        pos = writes = reads = 0
        calls, exits = [], []
        def syscall(u, _, __):
            nonlocal actual, pos, writes, reads
            nr = u.reg_read(UC_ARM_REG_R7)
            a,b,c = [u.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
            calls.append(nr)
            ret = 0
            if nr == 5:
                assert bytes(u.mem_read(a, len(target)+1)) == target.encode()+b'\0' and b == 2
                ret = -30 if scenario == 'open_denied' else 3
            elif nr == 100:
                assert a == 3
                u.mem_write(b, struct.pack('<I', 0xef53 if scenario == 'wrong_fs' else 0x01021994) + bytes(60))
                ret = -5 if scenario == 'statfs_failed' else 0
            elif nr == 197:
                assert a == 3
                stat = bytearray(104)
                struct.pack_into('<II', stat, 16, 0o040700 if scenario == 'not_regular' else 0o100600, 2 if scenario == 'hardlinked' else 1)
                struct.pack_into('<Q', stat, 48, 1284 if scenario == 'wrong_size' else 1283)
                u.mem_write(b, bytes(stat))
                ret = -5 if scenario == 'stat_failed' else 0
            elif nr == 19:
                assert a == 3 and b in (0, offset) and c == 0
                pos = b
                ret = -5 if scenario == 'seek_failed' else pos
            elif nr == 3:
                assert a == 3 and c == 1283
                reads += 1
                ret = -5 if scenario == 'read_failed' or scenario == 'reread_failed' and reads > 1 else 1282 if scenario == 'short_read' else 1283
                if ret > 0:
                    data = actual[pos:pos+ret]
                    if scenario == 'reread_corrupt' and reads > 1:
                        data = bytes([data[0]^255]) + data[1:]
                    u.mem_write(b, data)
                    pos += ret
            elif nr == 4:
                assert a == 3 and pos == offset and c == size and writes == 0
                data = bytes(u.mem_read(b,c))
                assert data == after[offset:offset+size]
                writes += 1
                ret = -5 if scenario == 'write_failed' else 3 if scenario == 'short_write' else size
                if ret > 0:
                    actual = actual[:pos] + data[:ret] + actual[pos+ret:]
                    pos += ret
            elif nr == 118:
                assert a == 3 and writes == 1
                ret = -5 if scenario == 'sync_failed' else 0
            elif nr == 6:
                assert a == 3
                ret = -5 if scenario == 'close_failed' else 0
            elif nr == 1:
                exits.append(a)
                u.emu_stop()
            else:
                raise AssertionError(('unapproved syscall', nr))
            u.reg_write(UC_ARM_REG_R0, ret & 0xffffffff)
        u.hook_add(UC_HOOK_INTR, syscall)
        u.emu_start(ENTRY, 0, count=50000)
        assert len(exits) == 1 and (exits[0] == 0) == (scenario == 'ok'), (scenario, exits)
        assert len(actual) == len(before) and actual[:offset] == initial[:offset] and actual[offset+size:] == initial[offset+size:]
        if scenario == 'ok':
            assert actual == after
        if scenario in scenarios[:12] and scenario != 'ok':
            assert not writes and actual == initial
        rows.append(dict(scenario=scenario, exitcode=exits[0], syscalls=calls, write_calls=writes,
                         length_preserved=True, outside_patch_preserved=True))
    return rows
