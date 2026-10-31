
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
 ldr r0,[r9,#12]
 ldr r1,value_12
 cmp r0,r1
 bne fail
 ldr r0,[r9,#16]
 ldr r1,value_16
 cmp r0,r1
 bne fail
 ldr r0,[r9,#20]
 ldr r1,value_20
 cmp r0,r1
 bne fail
 ldr r0,[r9,#28]
 ldr r1,value_28
 cmp r0,r1
 bne fail
 adr r0,expected
 add r1,r9,#32
 ldr r2,width
 bl compare
 cmp r0,#0
 bne fail
 adr r0,desired
 ldr r1,width
 add r1,r1,#32
 add r1,r9,r1
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
stack_size: .word 440
frame_size: .word 432
read_size: .word 433
width: .word 200
value_4: .word 362841600
value_8: .word 200
value_24: .word 0
value_12: .word 1
value_16: .word 200
value_20: .word 200
value_28: .word 0

path: .asciz "/tmp_bt/csboot-v1/last.bin"
.balign 4
expected: .byte 9,171,31,0,77,192,31,0,89,201,31,0,5,233,31,0,17,235,31,0,181,27,32,0,217,27,32,0,29,32,32,0,81,34,32,0,149,38,32,0,197,42,32,0,193,45,32,0,33,48,32,0,93,51,32,0,161,55,32,0,157,58,32,0,109,61,32,0,177,65,32,0,173,68,32,0,29,73,32,0,25,76,32,0,165,78,32,0,205,81,32,0,177,84,32,0,129,87,32,0,125,90,32,0,229,93,32,0,93,96,32,0,45,99,32,0,209,101,32,0,161,104,32,0,49,127,33,0,209,133,34,0,93,136,34,0,45,139,34,0,253,141,34,0,37,145,34,0,245,147,34,0,5,151,34,0,169,153,34,0,229,156,34,0,201,159,34,0,241,162,34,0,237,165,34,0,65,169,34,0,1,173,34,0,165,175,34,0,161,187,34,0,205,231,34,0,17,34,35,0
.balign 4
desired: .byte 112,181,130,176,4,70,0,240,39,248,212,248,44,1,39,245,186,228,1,70,32,70,106,70,0,35,0,147,112,245,62,252,0,152,1,40,21,211,6,40,19,216,1,56,14,166,6,235,0,22,212,248,56,33,0,42,9,73,0,208,9,73,32,70,33,245,118,226,39,245,56,227,0,40,2,208,49,70,65,245,146,249,0,32,2,176,112,189,45,233,240,71,112,245,18,191,59,64,59,185,128,26,171,1,69,49,48,48,0,0,0,0,0,0,0,0,0,0,0,0,82,69,65,76,65,0,0,0,0,0,0,0,0,0,0,0,67,50,48,48,0,0,0,0,0,0,0,0,0,0,0,0,71,111,108,100,32,50,48,48,0,0,0,0,0,0,0,0,80,82,79,86,73,65,0,0,0,0,0,0,0,0,0,0,72,80,53,0,0,0,0,0,0,0,0,0,0,0,0,0
