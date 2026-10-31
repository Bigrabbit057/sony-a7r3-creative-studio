
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
 ldr r0,[r9,#4]
 ldr r1,value_4
 cmp r0,r1
 bne fail
 ldr r0,[r9,#8]
 ldr r1,value_8
 cmp r0,r1
 bne fail
 ldr r0,[r9,#24]
 ldr r1,value_24
 cmp r0,r1
 bne fail
 adr r0,expected
 add r1,r9,#32
 ldr r2,width
 bl compare
 cmp r0,#0
 bne fail

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
stack_size: .word 48
frame_size: .word 40
read_size: .word 41
width: .word 4
value_4: .word 360158336
value_8: .word 4
value_24: .word 0

path: .asciz "/tmp_bt/csboot-v1/last.bin"
.balign 4
expected: .byte 143,242,190,184
.balign 4
desired: .byte 143,242,190,184
