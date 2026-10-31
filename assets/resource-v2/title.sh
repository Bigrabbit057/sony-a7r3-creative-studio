#!/bin/ash
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
