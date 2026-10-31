
    push {r4,r5,r6,lr}
    sub sp,#8
    mov r4,r0
    bl trampoline
    ldr.w r0,[r4,#0x12c]
    blx #0x159f84
    mov r1,r0
    mov r0,r4
    mov r2,sp
    movs r3,#0
    str r3,[sp]
    bl #0x5a2e9c
    ldr r0,[sp]
    cmp r0,#1
    blo done
    cmp r0,#6
    bhi done
    subs r0,#1
    adr r6,names
    add.w r6,r6,r0,lsl #4
    ldr.w r2,[r4,#0x138]
    cmp r2,#0
    ldr r1,title_normal
    beq chosen
    ldr r1,title_alt
chosen:
    mov r0,r4
    blx #0x153b30
    blx #0x159cb8
    cmp r0,#0
    beq done
    mov r1,r6
    bl #0x573976
done:
    movs r0,#0
    add sp,#8
    pop {r4,r5,r6,pc}
.balign 4
trampoline:
    push.w {r4,r5,r6,r7,r8,r9,r10,lr}
    b.w #5911684
.balign 4
title_normal: .word 0xb93b403b
title_alt: .word 0x01ab1a80
names:
.byte 69,49,48,48,0,0,0,0,0,0,0,0,0,0,0,0
.byte 82,69,65,76,65,0,0,0,0,0,0,0,0,0,0,0
.byte 67,50,48,48,0,0,0,0,0,0,0,0,0,0,0,0
.byte 71,111,108,100,32,50,48,48,0,0,0,0,0,0,0,0
.byte 80,82,79,86,73,65,0,0,0,0,0,0,0,0,0,0
.byte 72,80,53,0,0,0,0,0,0,0,0,0,0,0,0,0
