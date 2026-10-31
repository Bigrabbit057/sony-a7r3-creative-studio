
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
    mov r1,#2
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
size: .word 4
frame_size: .word 40
report_size: .word 40
address: .word 360158336
path: .asciz "/proc/158/mem"
.balign 4
expected: .byte 145,162,179,196
.balign 4
desired: .byte 51,68,85,102
