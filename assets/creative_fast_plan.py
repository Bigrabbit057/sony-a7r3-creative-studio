"""Batch-read / short-wait variant of the proven serialized AWB learner.

Does not depend on a UI hook. Keeps the same write/message/recovery contract.
Fast slot stability and slower manual-learning stability are separate.
"""
from creative_learning_plan import body as stable_body, ROOT

BATCH=r'''
cs_read_many() {
 local spec key width keys='' raw header hx lo hi n tail
 cs_many=''
 for spec in "$@"; do
  key=${spec%/*}; width=${spec#*/}
  case "$width" in 1|2) ;; *) return 1 ;; esac
  keys="$keys $key"
 done
 raw=$(/usr/bin/bk.elf r $keys)
 while [ "$#" -gt 0 ]; do
  spec=$1; shift; key=${spec%/*}; width=${spec#*/}
  IFS= read -r header && IFS= read -r hx || return 1
  [ "$header" = "id:${key#0x} size:$width data:" ] || return 1
  lo=${hx%%,*}; hi=''
  case "$width:${#hx}" in
   1:3) [ "$hx" = "$lo," ] || return 1 ;;
   2:6) hi=${hx#*,}; hi=${hi%,}; [ "$hx" = "$lo,$hi," ] && [ "${#hi}" = 2 ] || return 1 ;;
   *) return 1 ;;
  esac
  [ "${#lo}" = 2 ] || return 1
  case "$lo$hi" in *[!0-9A-Fa-f]*) return 1 ;; esac
  n=$((0x$lo))
  if [ "$width" = 1 ]; then [ "$n" -lt 128 ] || n=$((n-256))
  else n=$((n+256*0x$hi)); [ "$n" -lt 32768 ] || n=$((n-65536)); fi
  cs_many="$cs_many $n"
  if [ "$#" = 0 ]; then
   IFS= read -r tail && [ "$tail" = CS_BATCH_END ] || return 1
  fi
 done <<EOF
$raw
CS_BATCH_END
EOF
 # No ignored headers, truncated values or unexpected trailing output.
 [ "${#cs_many}" -gt 0 ]
}
cs_read() {
 cs_read_many "$1/$2" || return 1
 echo "${cs_many# }"
}
cs_mark() {
 local cs_time cs_unused
 read cs_time cs_unused </proc/uptime || cs_time=unknown
 echo "CS_TIME $cs_time $*"
}
'''

SAMPLE=r'''
cs_decode_wb() {
 [ "$#" = 10 ] && [ "$1" = 1 ] && [ "${10}" = 1 ] || return 1
 [ "$2 $3 $4 $5" = "$6 $7 $8 $9" ] || return 1
 cs_sa=$(($2*1000+$4)); cs_sc=$(($3*1000+$5))
 cs_valid "$cs_sa" "$cs_sc" || return 1
 [ "$2" -eq "$((cs_sa/1000))" ] && [ "$3" -eq "$((cs_sc/1000))" ]
}
cs_wb() {
 cs_read_many 0x01070019/1 0x01070017/1 0x01070016/1 0x010714b6/2 0x010714b5/2 0x0107067f/1 0x0107067e/1 0x010714dd/2 0x010714dc/2 0x01070019/1 || return 1
 cs_decode_wb $cs_many
}
cs_sample() {
 cs_read_many 0x01070762/1 0x0107031c/1 0x01070019/1 0x01070017/1 0x01070016/1 0x010714b6/2 0x010714b5/2 0x0107067f/1 0x0107067e/1 0x010714dd/2 0x010714dc/2 0x01070019/1 0x01070762/1 0x0107031c/1 || return 1
 set -- $cs_many
 [ "$#" = 14 ] || return 1
 case "$1" in 0|1|2|3|4|5) ;; *) return 2 ;; esac
 [ "$2" = 0 ] && [ "${14}" = 0 ] || return 2
 [ "$1" = "${13}" ] || return 1
 cs_ss=$1
 cs_decode_wb "$3" "$4" "$5" "$6" "$7" "$8" "$9" "${10}" "${11}" "${12}"
}
'''

def body():
    text=stable_body().decode('ascii')
    start=text.index('cs_read() {');end=text.index('cs_valid() {')
    text=text[:start]+BATCH+text[end:]
    start=text.index('cs_wb() {');end=text.index('cs_write() {')
    text=text[:start]+SAMPLE+text[end:]
    text=text.replace('local a=$1 c=$2 ai ci af cf cmdpid waited rc','local a=$1 c=$2 ai ci af cf cmdpid waited rc verify_try')
    text=text.replace(' /usr/bin/testcmd.elf --sync',' cs_mark SEND "$a" "$c"\n /usr/bin/testcmd.elf --sync')
    text=text.replace('[ "$waited" -lt 5 ]; do /bin/busybox sleep 1;', '[ "$waited" -lt 50 ]; do /bin/busybox usleep 100000;')
    old=' /bin/busybox sleep 2\n cs_wb && [ "$cs_sa $cs_sc" = "$a $c" ]'
    new=''' verify_try=0
 while [ "$verify_try" -lt 20 ]; do
  if cs_wb && [ "$cs_sa $cs_sc" = "$a $c" ]; then cs_mark VERIFIED "$a" "$c"; return 0; fi
  /bin/busybox usleep 100000; verify_try=$((verify_try+1))
 done
 return 1'''
    assert old in text;text=text.replace(old,new)
    text=text.replace('/bin/busybox sleep 1','/bin/busybox usleep 250000')
    text=text.replace('cs_resume=0\ncs_save', 'cs_resume=0; cs_equal=0\ncs_save')
    text=text.replace('[ "$cs_invalid" -eq 10 ]','[ "$cs_invalid" -eq 40 ]')
    text=text.replace("  cs_previous=''; cs_invalid=", "  cs_previous=''; cs_equal=0; cs_invalid=")
    text=text.replace('  cs_previous=$cs_signature; /bin/busybox usleep 250000; continue', '''  if [ "$cs_ss" != "$cs_last" ]; then cs_mark CANDIDATE "$cs_ss"; fi
  cs_previous=$cs_signature; cs_equal=0; /bin/busybox usleep 250000; continue''')
    text=text.replace(' if [ "$cs_resume" = 1 ]; then', ' cs_equal=$((cs_equal+1))\n if [ "$cs_resume" = 1 ]; then')
    needle='  if [ "$cs_sa $cs_sc" != "$cs_olda $cs_oldc" ]; then\n   cs_store'
    assert needle in text
    text=text.replace(needle,'''  if [ "$cs_sa $cs_sc" != "$cs_olda $cs_oldc" ]; then
   # Manual edits need four further stable samples (~1 s), independent of
   # the shorter slot-switch guard. Never learn during our own transaction.
   if [ "$cs_equal" -lt 4 ]; then /bin/busybox usleep 250000; continue; fi
   cs_store''')
    text=text.replace('  if cs_apply "$cs_newa" "$cs_newc"; then', '  cs_mark APPLY "$cs_next" "$cs_newa" "$cs_newc"\n  if [ "$cs_newa $cs_newc" = "$cs_olda $cs_oldc" ] || cs_apply "$cs_newa" "$cs_newc"; then')
    text=text.replace('echo CS_ARMED','echo CS_VARIANT_BATCH_FAST_V1\necho CS_ARMED')
    assert '/bin/busybox sleep' not in text and text.isascii()
    return text.encode('ascii')

if __name__=='__main__':
    (ROOT/'results/creative-learning-fast.sh').write_bytes(body())
    print('Fast candidate generated; no camera access')
