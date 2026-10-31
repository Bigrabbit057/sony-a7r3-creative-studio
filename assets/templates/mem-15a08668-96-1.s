
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
size: .word 96
frame_size: .word 224
report_size: .word 224
address: .word 362841704
path: .asciz "/proc/158/mem"
.balign 4
expected: .byte 145,162,179,196,213,230,247,8,25,42,59,76,93,110,127,144,161,178,195,212,229,246,7,24,41,58,75,92,109,126,143,160,177,194,211,228,245,6,23,40,57,74,91,108,125,142,159,176,193,210,227,244,5,22,39,56,73,90,107,124,141,158,175,192,209,226,243,4,21,38,55,72,89,106,123,140,157,174,191,208,225,242,3,20,37,54,71,88,105,122,139,156,173,190,207,224
.balign 4
desired: .byte 51,68,85,102,119,136,153,170,187,204,221,238,255,16,33,50,67,84,101,118,135,152,169,186,203,220,237,254,15,32,49,66,83,100,117,134,151,168,185,202,219,236,253,14,31,48,65,82,99,116,133,150,167,184,201,218,235,252,13,30,47,64,81,98,115,132,149,166,183,200,217,234,251,12,29,46,63,80,97,114,131,148,165,182,199,216,233,250,11,28,45,62,79,96,113,130
