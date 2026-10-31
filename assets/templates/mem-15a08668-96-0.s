
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
    mov r1,#0
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
desired: .byte 145,162,179,196,213,230,247,8,25,42,59,76,93,110,127,144,161,178,195,212,229,246,7,24,41,58,75,92,109,126,143,160,177,194,211,228,245,6,23,40,57,74,91,108,125,142,159,176,193,210,227,244,5,22,39,56,73,90,107,124,141,158,175,192,209,226,243,4,21,38,55,72,89,106,123,140,157,174,191,208,225,242,3,20,37,54,71,88,105,122,139,156,173,190,207,224
