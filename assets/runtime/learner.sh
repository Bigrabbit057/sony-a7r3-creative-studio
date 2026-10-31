#!/bin/ash
# Only AWB menu offsets are learned, never measured AWB color gains.
# No runtime/transition cap. Only changed offsets are saved in RAM.
cs_dir=${0%/*}
cs_a0=-1000; cs_c0=0
cs_a1=0; cs_c1=0
cs_a2=-1000; cs_c2=-1000
cs_a3=3000; cs_c3=-1000
cs_a4=0; cs_c4=0
cs_a5=0; cs_c5=0
cs_load() {
 case "$1" in
0) cs_ab=$cs_a0; cs_cc=$cs_c0 ;;
1) cs_ab=$cs_a1; cs_cc=$cs_c1 ;;
2) cs_ab=$cs_a2; cs_cc=$cs_c2 ;;
3) cs_ab=$cs_a3; cs_cc=$cs_c3 ;;
4) cs_ab=$cs_a4; cs_cc=$cs_c4 ;;
5) cs_ab=$cs_a5; cs_cc=$cs_c5 ;;
 *) return 1 ;;
 esac
}
cs_store() {
 case "$1" in
0) cs_a0=$2; cs_c0=$3 ;;
1) cs_a1=$2; cs_c1=$3 ;;
2) cs_a2=$2; cs_c2=$3 ;;
3) cs_a3=$2; cs_c3=$3 ;;
4) cs_a4=$2; cs_c4=$3 ;;
5) cs_a5=$2; cs_c5=$3 ;;
 *) return 1 ;;
 esac
}
cs_save() {
 local i
 : >"$cs_dir/state.new" || return 1
 for i in 0 1 2 3 4 5; do
  cs_load "$i" || return 1
  echo "$i $cs_ab $cs_cc" >>"$cs_dir/state.new" || return 1
 done
 /bin/busybox mv "$cs_dir/state.new" "$cs_dir/state.tsv"
}

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
cs_valid() {
 [ "$1" -ge -7000 ] && [ "$1" -le 7000 ] && [ "$(( $1%500 ))" -eq 0 ] &&
 [ "$2" -ge -7000 ] && [ "$2" -le 7000 ] && [ "$(( $2%250 ))" -eq 0 ]
}

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
cs_write() {
 local k=$1 n=$2 width=$3
 if [ "$width" = 1 ]; then
  /usr/bin/bk.elf w "$k" "$(cs_hex "$((n&255))" 2)" >/dev/null
 else
  /usr/bin/bk.elf w "$k" "$(cs_hex "$((n&255))" 2)" "$(cs_hex "$(((n>>8)&255))" 2)" >/dev/null
 fi
 [ "$(cs_read "$k" "$width")" = "$n" ]
}
cs_hex() {
 local n=$1 length=$2 out='' digit
 while [ "$length" -gt 0 ]; do
  digit=$((n&15))
  case "$digit" in 10) digit=A ;; 11) digit=B ;; 12) digit=C ;; 13) digit=D ;; 14) digit=E ;; 15) digit=F ;; esac
  out=$digit$out; n=$((n>>4)); length=$((length-1))
 done
 echo "$out"
}
cs_h32() { echo "0x$(cs_hex "$1" 8)"; }
cs_apply() {
 local a=$1 c=$2 ai ci af cf cmdpid waited rc verify_try
 cs_valid "$a" "$c" || return 1
 ai=$((a/1000)); ci=$((c/1000)); af=$((a-ai*1000)); cf=$((c-ci*1000))
 cs_write 0x0107067f "$ai" 1 && cs_write 0x0107067e "$ci" 1 && cs_write 0x010714dd "$af" 2 && cs_write 0x010714dc "$cf" 2 || return 1
 cs_mark SEND "$a" "$c"
 /usr/bin/testcmd.elf --sync 0x83014b 0x11004003 0x1 0x6 0x0 0x1 0x7 0xb 0x1 0x8 0x1200b012 0x1 0x136 0x1 0x1 0x139 "$(cs_h32 "$ai")" 0x1 0x13c "$(cs_h32 "$ci")" 0x1 0x4e4 "$(cs_h32 "$af")" 0x1 0x4e7 "$(cs_h32 "$cf")" </dev/null & cmdpid=$!
 waited=0
 while kill -0 "$cmdpid" 2>/dev/null && [ "$waited" -lt 50 ]; do /bin/busybox usleep 100000; waited=$((waited+1)); done
 if kill -0 "$cmdpid" 2>/dev/null; then kill "$cmdpid"; wait "$cmdpid"; echo CS_REQUEST_TIMEOUT; return 1; fi
 wait "$cmdpid"; rc=$?
 [ "$rc" = 0 ] || return 1
 verify_try=0
 while [ "$verify_try" -lt 20 ]; do
  if cs_wb && [ "$cs_sa $cs_sc" = "$a $c" ]; then cs_mark VERIFIED "$a" "$c"; return 0; fi
  /bin/busybox usleep 100000; verify_try=$((verify_try+1))
 done
 return 1
}
cs_mixed() {
 local a=$1 c=$2 b=$3 d=$4 k width x old new i=0
 [ "$(cs_read 0x01070019 1)" = 1 ] && [ "$(cs_read 0x0107031c 1)" = 0 ] || return 1
 for k in 0x01070017 0x01070016 0x010714b6 0x010714b5 0x0107067f 0x0107067e 0x010714dd 0x010714dc; do
  case "$((i%4))" in
   0) width=1; old=$((a/1000)); new=$((b/1000)) ;;
   1) width=1; old=$((c/1000)); new=$((d/1000)) ;;
   2) width=2; old=$((a-a/1000*1000)); new=$((b-b/1000*1000)) ;;
   3) width=2; old=$((c-c/1000*1000)); new=$((d-d/1000*1000)) ;;
  esac
  x=$(cs_read "$k" "$width") || return 1
  [ "$x" = "$old" ] || [ "$x" = "$new" ] || return 1
  i=$((i+1))
 done
}
# The seed is data, not executable code. The host preserves collected slot
# memories and explicitly seeds the user's current confirmed manual setting.
if [ -f "$cs_dir/state.tsv" ]; then
 cs_rows=0
 while read cs_i cs_a cs_c cs_extra; do
  if [ "$cs_i" != "$cs_rows" ] || [ -n "$cs_extra" ] || ! cs_valid "$cs_a" "$cs_c"; then echo CS_BAD_SEED; echo CS_DONE; exit 1; fi
  cs_store "$cs_i" "$cs_a" "$cs_c" || exit 1
  cs_rows=$((cs_rows+1))
 done <"$cs_dir/state.tsv"
 [ "$cs_rows" = 6 ] || { echo CS_BAD_SEED; echo CS_DONE; exit 1; }
fi
cs_failed=0; cs_count=0; cs_learned=0; cs_last=''; cs_previous=''; cs_invalid=0; cs_ready=0; cs_resume=0; cs_equal=0
cs_save || { echo CS_STATE_SAVE_FAILED; echo CS_DONE; exit 1; }
echo CS_VARIANT_AUTOSTART_V1
echo CS_ARMED
while [ -f "$cs_dir/enabled" ]; do
 if ! cs_sample; then
  cs_previous=''; cs_equal=0; cs_invalid=$((cs_invalid+1))
  # No writes while a menu is updating, PP is enabled, or WB leaves AWB.
  # A menu or unsupported mode pauses writes; returning can resume without
  # confusing settings changed elsewhere with an edit to a recipe.
  if [ "$cs_invalid" -eq 40 ]; then echo CS_PAUSED_UNSUPPORTED_OR_UNSTABLE; cs_resume=1; fi
  /bin/busybox usleep 250000; continue
 fi
 cs_invalid=0
 if [ "$cs_ready" = 0 ]; then echo CS_SAMPLE_READY; cs_ready=1; fi
 if [ -z "$cs_last" ]; then
  cs_boot_signature="$cs_ss $cs_sa $cs_sc"
  if [ "$cs_boot_signature" != "$cs_boot_previous" ]; then cs_boot_previous=$cs_boot_signature; cs_boot_equal=0; fi
  cs_boot_equal=$((cs_boot_equal+1))
  if [ "$cs_boot_equal" -lt 8 ]; then /bin/busybox usleep 250000; continue; fi
  cs_load "$cs_ss" || { cs_failed=1; break; }
  if [ "$cs_sa $cs_sc" != "$cs_ab $cs_cc" ]; then
   cs_apply "$cs_ab" "$cs_cc" || { echo CS_BOOT_APPLY_FAILED; cs_failed=1; break; }
  fi
  cs_last=$cs_ss; cs_activea=$cs_ab; cs_activec=$cs_cc
  echo "CS_BOOT_RECIPE $cs_last $cs_activea $cs_activec"
  cs_previous=''; continue
 fi
 cs_signature="$cs_ss $cs_sa $cs_sc"
 if [ "$cs_signature" != "$cs_previous" ]; then
  if [ "$cs_ss" != "$cs_last" ]; then cs_mark CANDIDATE "$cs_ss"; fi
  cs_previous=$cs_signature; cs_equal=0; /bin/busybox usleep 250000; continue
 fi
 cs_equal=$((cs_equal+1))
 if [ "$cs_resume" = 1 ]; then
  cs_last=$cs_ss; cs_activea=$cs_sa; cs_activec=$cs_sc; cs_resume=0
  echo "CS_OBSERVE $cs_last $cs_activea $cs_activec"
  /bin/busybox usleep 250000; continue
 fi
 cs_olda=$cs_activea; cs_oldc=$cs_activec
 if [ "$cs_ss" = "$cs_last" ]; then
  if [ "$cs_sa $cs_sc" != "$cs_olda $cs_oldc" ]; then
   # Manual edits need four further stable samples (~1 s), independent of
   # the shorter slot-switch guard. Never learn during our own transaction.
   if [ "$cs_equal" -lt 4 ]; then /bin/busybox usleep 250000; continue; fi
   cs_store "$cs_last" "$cs_sa" "$cs_sc" && cs_save || { echo CS_STATE_SAVE_FAILED; cs_failed=1; break; }
   cs_activea=$cs_sa; cs_activec=$cs_sc
   cs_learned=$((cs_learned+1)); echo "CS_LEARN $cs_last $cs_sa $cs_sc"
  fi
 else
  if [ "$cs_sa $cs_sc" != "$cs_olda $cs_oldc" ]; then
   # Cannot know which slot owns an edit made between polls. Preserve both
   # caches and the visible WB, re-anchor observation, follow the next switch.
   echo "CS_RESYNC_PRESERVED $cs_last $cs_olda $cs_oldc -> $cs_ss $cs_sa $cs_sc"
   cs_last=$cs_ss; cs_activea=$cs_sa; cs_activec=$cs_sc
   /bin/busybox usleep 250000; continue
  fi
  cs_next=$cs_ss; cs_load "$cs_next" || { cs_failed=1; break; }
  cs_newa=$cs_ab; cs_newc=$cs_cc
  [ -f "$cs_dir/enabled" ] || break
  if [ "$(cs_read 0x01070762 1)" != "$cs_next" ] || [ "$(cs_read 0x0107031c 1)" != 0 ]; then cs_previous=''; continue; fi
  echo "CS_BATCH $cs_last $cs_next $cs_olda $cs_oldc -> $cs_newa $cs_newc"
  cs_mark APPLY "$cs_next" "$cs_newa" "$cs_newc"
  if [ "$cs_newa $cs_newc" = "$cs_olda $cs_oldc" ] || cs_apply "$cs_newa" "$cs_newc"; then
   cs_last=$cs_next; cs_activea=$cs_newa; cs_activec=$cs_newc; cs_count=$((cs_count+1)); cs_previous=''; echo "CS_RECIPE_OK_$cs_last"
  else
   echo CS_APPLY_FAILED; cs_failed=1
   if cs_mixed "$cs_olda" "$cs_oldc" "$cs_newa" "$cs_newc"; then
    if cs_apply "$cs_olda" "$cs_oldc"; then echo CS_RECOVERY_OK; else echo CS_RECOVERY_UNCONFIRMED; fi
   else echo CS_EXTERNAL_CHANGE_PRESERVED; fi
   break
  fi
 fi
 /bin/busybox usleep 250000
done
echo CS_COUNT=$cs_count; echo CS_LEARNED=$cs_learned; echo CS_FAILED=$cs_failed; echo CS_DONE
