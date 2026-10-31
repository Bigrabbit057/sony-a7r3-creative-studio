#!/bin/ash
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
check_file /usr/lib/viewUnified2.so 642ec1fe93e49f02fe19f4455bd429b8 || exit 19
check_file /usr/share/app/string_simplifiedchinese.uxc a93646cb3495574c92ccc31be6b83544 || exit 19
check_file /usr/bin/bk.elf 906081a186bdd76caa4df7bf6b33f2eb || exit 19
check_file "$P/common.sh" df413dd95b1337db8b182bfd15377e0f || exit 18
check_file "$P/title.sh" 42d235ba5f7482d96d01365da2a53695 || exit 18
check_file "$P/learner.sh" 6e66fc938ff6e0a9ecc76c5977391762 || exit 18
check_file "$P/entry-original.elf" bbb8e8b659345be1910195475ada0f1e || exit 18
check_file "$P/ok-entry-original.elf" 9e6a4b786d838635e5d2abb433c6eb1a || exit 18
check_file "$P/entry-installed.elf" 8618517465ffd9b5b3fa3b4022fb9a04 || exit 18
check_file "$P/ok-entry-installed.elf" 75c9c5ed59f9d86486b3c50c02a04ba8 || exit 18
check_file "$P/cave-original.elf" ac107f79d2d561277dac6c9fdc6ce144 || exit 18
check_file "$P/ok-cave-original.elf" accc248d5257efe5a133e75dbdbb6c53 || exit 18
check_file "$P/cave-installed.elf" ad0a07cbbaccb5d8a266cbffb1962366 || exit 18
check_file "$P/ok-cave-installed.elf" e852f7982fd9170d665d88554cf6b298 || exit 18
check_file "$P/clear-original.elf" cf75e0b33d7ec89906cd2270db3bb555 || exit 18
check_file "$P/ok-clear-original.elf" 3144f3b21d83cbe916b13eb997d3e08e || exit 18
check_file "$P/alias.elf" f60646b225086e9ea0a5cd0ec027d1ad || exit 18
check_file "$P/ok-alias.elf" ef98da8baaec96893276ed5d5cce046e || exit 18
check_file "$P/stage.elf" 23296d35488aa073d5b1621729ae8d40 || exit 18
check_file "$P/ok-stage.elf" 079d145bead4d3ebbf73a3f6c96d90e9 || exit 18
check_file "$P/enable.elf" 2b9cadb9a0ea9158bbf6a1dbc1be234e || exit 18
check_file "$P/ok-enable.elf" 3b39b5006779fb31184ad9470217df64 || exit 18
check_file "$P/disable.elf" 201ef734e86de1b2e36308b5e26273dc || exit 18
check_file "$P/ok-disable.elf" cb1f7a9f4bfc063837a37e9915c62406 || exit 18
. "$P/common.sh" || exit 20
# Refuse concurrent legacy white-balance writers. No automatic killing.
for d in /tmp_bt/ppstudio-* /tmp_bt/pp-three-* /tmp_bt/creative-recipes-*; do
 if [ -f "$d/enabled" ]; then echo CSBOOT_OTHER_FOLLOWER; exit 21; fi
done
/bin/busybox cp "$P/entry-original.elf" "$R/entry-original.elf" && /bin/busybox chmod 700 "$R/entry-original.elf" || exit 27
/bin/busybox cp "$P/ok-entry-original.elf" "$R/ok-entry-original.elf" && /bin/busybox chmod 700 "$R/ok-entry-original.elf" || exit 27
/bin/busybox cp "$P/entry-installed.elf" "$R/entry-installed.elf" && /bin/busybox chmod 700 "$R/entry-installed.elf" || exit 27
/bin/busybox cp "$P/ok-entry-installed.elf" "$R/ok-entry-installed.elf" && /bin/busybox chmod 700 "$R/ok-entry-installed.elf" || exit 27
/bin/busybox cp "$P/cave-original.elf" "$R/cave-original.elf" && /bin/busybox chmod 700 "$R/cave-original.elf" || exit 27
/bin/busybox cp "$P/ok-cave-original.elf" "$R/ok-cave-original.elf" && /bin/busybox chmod 700 "$R/ok-cave-original.elf" || exit 27
/bin/busybox cp "$P/cave-installed.elf" "$R/cave-installed.elf" && /bin/busybox chmod 700 "$R/cave-installed.elf" || exit 27
/bin/busybox cp "$P/ok-cave-installed.elf" "$R/ok-cave-installed.elf" && /bin/busybox chmod 700 "$R/ok-cave-installed.elf" || exit 27
/bin/busybox cp "$P/clear-original.elf" "$R/clear-original.elf" && /bin/busybox chmod 700 "$R/clear-original.elf" || exit 27
/bin/busybox cp "$P/ok-clear-original.elf" "$R/ok-clear-original.elf" && /bin/busybox chmod 700 "$R/ok-clear-original.elf" || exit 27
/bin/busybox cp "$P/alias.elf" "$R/alias.elf" && /bin/busybox chmod 700 "$R/alias.elf" || exit 27
/bin/busybox cp "$P/ok-alias.elf" "$R/ok-alias.elf" && /bin/busybox chmod 700 "$R/ok-alias.elf" || exit 27
/bin/busybox cp "$P/stage.elf" "$R/stage.elf" && /bin/busybox chmod 700 "$R/stage.elf" || exit 27
/bin/busybox cp "$P/ok-stage.elf" "$R/ok-stage.elf" && /bin/busybox chmod 700 "$R/ok-stage.elf" || exit 27
/bin/busybox cp "$P/enable.elf" "$R/enable.elf" && /bin/busybox chmod 700 "$R/enable.elf" || exit 27
/bin/busybox cp "$P/ok-enable.elf" "$R/ok-enable.elf" && /bin/busybox chmod 700 "$R/ok-enable.elf" || exit 27
/bin/busybox cp "$P/disable.elf" "$R/disable.elf" && /bin/busybox chmod 700 "$R/disable.elf" || exit 27
/bin/busybox cp "$P/ok-disable.elf" "$R/ok-disable.elf" && /bin/busybox chmod 700 "$R/ok-disable.elf" || exit 27
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
