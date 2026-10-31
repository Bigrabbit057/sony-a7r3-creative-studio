"""Offline templates for scoped Creative Style autoload. No camera access."""
from creative_fast_plan import body as fast_body

PERSIST='/setting/csboot-v1'
RAM='/tmp_bt/csboot-v1'
BRIDGE='/setting/cs'
TOKEN='CSBOOT_CREATIVE_V1_20261027'

COMMON=r'''#!/bin/ash
P=/setting/csboot-v1
R=/tmp_bt/csboot-v1
cs_integer() {
 local n=$1
 case "$n" in -*) n=${n#-} ;; esac
 case "$n" in ''|*[!0-9]*) return 1 ;; esac
 [ "${#n}" -le 4 ] || return 1
 case "$n" in 0[0-9]*) return 1 ;; esac
}
cs_rows() {
 local i a c extra count=0
 J_ROWS=''
 while read -r i a c extra; do
  [ "$i" = "$count" ] && [ -z "$extra" ] || return 1
  cs_integer "$a" && cs_integer "$c" || return 1
  [ "$a" -ge -7000 ] && [ "$a" -le 7000 ] && [ "$((a%500))" = 0 ] || return 1
  [ "$c" -ge -7000 ] && [ "$c" -le 7000 ] && [ "$((c%250))" = 0 ] || return 1
  J_ROWS="$J_ROWS$i $a $c
"
  count=$((count+1))
 done
 [ "$count" = 6 ]
}
cs_record_read() {
 local file=$1 tag seq extra i=0 a c line digest calculated rows=''
 J_SEQ=-1; J_ROWS=''
 [ -f "$file" ] && [ ! -L "$file" ] || return 1
 {
  read -r tag seq extra || return 1
  [ "$tag" = CSWB1 ] && [ -z "$extra" ] || return 1
  case "$seq" in ''|*[!0-9]*|0[0-9]*) return 1 ;; esac
  [ "${#seq}" -le 9 ] || return 1
  while [ "$i" -lt 6 ]; do
   read -r tag a c extra || return 1
   [ "$tag" = "$i" ] && [ -z "$extra" ] || return 1
   rows="$rows$tag $a $c
"
   i=$((i+1))
  done
  read -r tag digest extra || return 1
  [ "$tag" = MD5 ] && [ -z "$extra" ] && [ "${#digest}" = 32 ] || return 1
  case "$digest" in *[!0-9a-f]*) return 1 ;; esac
  if read -r line; then return 1; fi
 } <"$file"
 cs_rows <<EOF
${rows%?}
EOF
 [ "$?" = 0 ] || return 1
 { echo "CSWB1 $seq"; echo "${J_ROWS%?}"; } >"$R/record-body" || return 1
 calculated=$(/bin/busybox md5sum "$R/record-body"); calculated=${calculated%% *}
 [ "$digest" = "$calculated" ] || return 1
 J_SEQ=$seq
}
cs_select() {
 local best=-1 rows='' active=''
 if cs_record_read "$P/slots.a"; then best=$J_SEQ; rows=$J_ROWS; active=a; fi
 if cs_record_read "$P/slots.b" && [ "$J_SEQ" -gt "$best" ]; then best=$J_SEQ; rows=$J_ROWS; active=b; fi
 [ "$best" -ge 0 ] || return 1
 J_SEQ=$best; J_ROWS=$rows; J_ACTIVE=$active
}
cs_commit() {
 local newrows=$1 next target digest
 [ "$J_SEQ" -lt 999999999 ] || return 1
 cs_rows <<EOF
${newrows%?}
EOF
 [ "$?" = 0 ] || return 1
 next=$((J_SEQ+1))
 if [ "$J_ACTIVE" = a ]; then target=b; else target=a; fi
 { echo "CSWB1 $next"; echo "${J_ROWS%?}"; } >"$R/record-new" || return 1
 digest=$(/bin/busybox md5sum "$R/record-new"); digest=${digest%% *}
 echo "MD5 $digest" >>"$R/record-new" || return 1
 # Overwrite only the inactive owned record; the other validated copy remains.
 /bin/busybox cp "$R/record-new" "$P/slots.$target" && /bin/busybox sync || return 1
 cs_record_read "$P/slots.$target" && [ "$J_SEQ" = "$next" ] && [ "$J_ROWS" = "$newrows" ] || return 1
 J_ACTIVE=$target
 echo "CSBOOT_SAVED $J_SEQ $J_ACTIVE"
}
'''

TITLE=r'''#!/bin/ash
P=/setting/csboot-v1
R=/tmp_bt/csboot-v1
ui_identity() {
 local line rest
 read -r line </proc/158/stat || return 1
 case "$line" in '158 (im.elf) '*) ;; *) return 1 ;; esac
 rest=${line#*) }; set -- $rest
 shift 19
 [ "$1" = 125 ] || return 1
 /bin/busybox grep -q '^151d6000-15a09000 r-xp 00000000 .* /usr/lib/viewUnified2\.so$' /proc/158/maps &&
 /bin/busybox grep -q '^15a10000-15c1f000 rw-p 00832000 .* /usr/lib/viewUnified2\.so$' /proc/158/maps
}
run_title() {
 ui_identity || return 1
 "$R/$1.elf" >"$R/last.bin" && "$R/ok-$1.elf"
}
ui_identity || { echo CSBOOT_TITLE_IDENTITY_REFUSED; exit 10; }
if run_title entry-installed; then
 run_title cave-installed || exit 11
 echo CSBOOT_TITLES_ALREADY_READY
 exit 0
fi
# Slot labels are embedded in our private hook table, not in the movable
# language-resource mapping. The old global Clear-string probe was left over
# from an earlier experiment and must not gate or address that mapping here.
# Keep the exact UI code/data mappings and entry/cave byte guards.
run_title entry-original && run_title cave-original || exit 12
run_title alias && /bin/busybox cp "$R/last.bin" "$R/alias-before.bin" || exit 13
run_title stage && run_title cave-installed || exit 14
run_title alias && /bin/busybox cmp -s "$R/last.bin" "$R/alias-before.bin" || exit 15
if ! run_title enable; then
 run_title disable
 exit 16
fi
run_title entry-installed && run_title cave-installed || exit 17
echo CSBOOT_TITLES_READY
'''

BOOT=r'''#!/bin/ash
P=/setting/csboot-v1
R=/tmp_bt/csboot-v1
[ -f "$P/enabled" ] && [ ! -L "$P/enabled" ] || exit 0
[ "$(cat "$P/enabled")" = CSBOOT_CREATIVE_V1_20261027 ] || exit 0
[ -d /tmp_bt ] || exit 0
# A single per-boot lock also suppresses duplicate Bluetooth wake invocations.
/bin/busybox mkdir -m 700 "$R" 2>/dev/null || exit 0
exec </dev/null >>"$R/boot.log" 2>&1
echo $$ >"$R/supervisor.pid"
cat /proc/sys/kernel/random/boot_id >"$R/boot-id"
echo CSBOOT_BEGIN
umask 077
check_file() {
 local actual
 [ -f "$1" ] && [ ! -L "$1" ] || return 1
 actual=$(/bin/busybox md5sum "$1"); actual=${actual%% *}
 [ "$actual" = "$2" ]
}
__HASH_CHECKS__
. "$P/common.sh" || exit 20
# Refuse concurrent legacy white-balance writers. No automatic killing.
for d in /tmp_bt/ppstudio-* /tmp_bt/pp-three-* /tmp_bt/creative-recipes-*; do
 if [ -f "$d/enabled" ]; then echo CSBOOT_OTHER_FOLLOWER; exit 21; fi
done
__COPY_HELPERS__
ready=0; n=0
while [ "$n" -lt 90 ]; do
 if [ -s /tmp_bt/bsa_s_pid ] && [ -f /proc/158/maps ]; then ready=1; break; fi
 n=$((n+1)); /bin/busybox sleep 1
done
[ "$ready" = 1 ] || { echo CSBOOT_NOT_READY; exit 22; }
/bin/ash "$P/title.sh"
title_rc=$?
[ "$title_rc" = 0 ] || { echo "CSBOOT_TITLE_FAILED rc=$title_rc"; exit 23; }
cs_select || { echo CSBOOT_NO_VALID_MEMORY; exit 24; }
last_rows=$J_ROWS
echo "${last_rows%?}" >"$R/state.tsv" || exit 25
/bin/busybox cp "$P/learner.sh" "$R/run.sh" || exit 26
echo CSBOOT_LEARNER >"$R/enabled"
/bin/ash "$R/run.sh" >>"$R/trace.txt" 2>&1 & child=$!
echo "$child" >"$R/learner.pid"
echo "CSBOOT_LEARNER_STARTED $child"
counter=0
while [ -f "$P/enabled" ] && kill -0 "$child" 2>/dev/null; do
 /bin/busybox sleep 2
 if [ -f "$R/state.tsv" ] && cs_rows <"$R/state.tsv"; then
  rows=$J_ROWS
  if [ "$rows" != "$last_rows" ]; then
   if cs_commit "$rows"; then last_rows=$rows; else echo CSBOOT_SAVE_FAILED; break; fi
  fi
 fi
 counter=$((counter+1))
 if [ "$counter" -ge 30 ]; then
  counter=0
  size=$(/bin/busybox wc -c <"$R/trace.txt")
  if [ "$size" -gt 65536 ]; then : >"$R/trace.txt"; echo CSBOOT_TRACE_TRIMMED; fi
  size=$(/bin/busybox wc -c <"$R/boot.log")
  if [ "$size" -gt 32768 ]; then : >"$R/boot.log"; echo CSBOOT_LOG_TRIMMED; fi
 fi
done
# Remove only our own follower enable flag and allow its bounded transaction to finish.
/bin/busybox rm -f "$R/enabled"
wait "$child"
echo CSBOOT_DONE
'''


def learner():
    text=fast_body().decode('ascii')
    old=''' if [ -z "$cs_last" ]; then
  cs_last=$cs_ss; cs_activea=$cs_sa; cs_activec=$cs_sc
  echo "CS_OBSERVE $cs_last $cs_activea $cs_activec"
 fi'''
    new=''' if [ -z "$cs_last" ]; then
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
 fi'''
    assert text.count(old)==1
    text=text.replace(old,new).replace('echo CS_VARIANT_BATCH_FAST_V1','echo CS_VARIANT_AUTOSTART_V1')
    return text.encode()
