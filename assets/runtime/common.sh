#!/bin/ash
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
