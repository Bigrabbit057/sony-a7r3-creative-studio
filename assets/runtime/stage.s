
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
size: .word 200
frame_size: .word 432
report_size: .word 432
address: .word 362841600
path: .asciz "/proc/158/mem"
.balign 4
expected: .byte 9,171,31,0,77,192,31,0,89,201,31,0,5,233,31,0,17,235,31,0,181,27,32,0,217,27,32,0,29,32,32,0,81,34,32,0,149,38,32,0,197,42,32,0,193,45,32,0,33,48,32,0,93,51,32,0,161,55,32,0,157,58,32,0,109,61,32,0,177,65,32,0,173,68,32,0,29,73,32,0,25,76,32,0,165,78,32,0,205,81,32,0,177,84,32,0,129,87,32,0,125,90,32,0,229,93,32,0,93,96,32,0,45,99,32,0,209,101,32,0,161,104,32,0,49,127,33,0,209,133,34,0,93,136,34,0,45,139,34,0,253,141,34,0,37,145,34,0,245,147,34,0,5,151,34,0,169,153,34,0,229,156,34,0,201,159,34,0,241,162,34,0,237,165,34,0,65,169,34,0,1,173,34,0,165,175,34,0,161,187,34,0,205,231,34,0,17,34,35,0
.balign 4
desired: .byte 112,181,130,176,4,70,0,240,39,248,212,248,44,1,39,245,186,228,1,70,32,70,106,70,0,35,0,147,112,245,62,252,0,152,1,40,21,211,6,40,19,216,1,56,14,166,6,235,0,22,212,248,56,33,0,42,9,73,0,208,9,73,32,70,33,245,118,226,39,245,56,227,0,40,2,208,49,70,65,245,146,249,0,32,2,176,112,189,45,233,240,71,112,245,18,191,59,64,59,185,128,26,171,1,69,49,48,48,0,0,0,0,0,0,0,0,0,0,0,0,82,69,65,76,65,0,0,0,0,0,0,0,0,0,0,0,67,50,48,48,0,0,0,0,0,0,0,0,0,0,0,0,71,111,108,100,32,50,48,48,0,0,0,0,0,0,0,0,80,82,79,86,73,65,0,0,0,0,0,0,0,0,0,0,72,80,53,0,0,0,0,0,0,0,0,0,0,0,0,0
