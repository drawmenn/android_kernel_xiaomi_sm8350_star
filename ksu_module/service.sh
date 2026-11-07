#!/system/bin/sh
# Boot-time service: wait for the kernel sysfs interface and the package
# manager, then apply the configured rules (see control.sh). Every
# attempt is logged to /data/adb/uid_path_filter_rules/apply.log.

MODDIR=${0%/*}
STORE=/data/adb/uid_path_filter_rules
LOG="$STORE/apply.log"

# Restore executable bits in case the blanket 0644 permission won.
[ -f "$MODDIR/magiskpolicy" ] && chmod 0755 "$MODDIR/magiskpolicy" 2>/dev/null
[ -f "$MODDIR/control.sh" ]   && chmod 0755 "$MODDIR/control.sh"   2>/dev/null

# Seed the config on first boot after install.
sh "$MODDIR/control.sh" init >/dev/null 2>&1

: > "$LOG"
echo "$(date '+%m-%d %H:%M:%S') service start (kernel $(uname -r 2>/dev/null))" >> "$LOG"

i=0
out=""
while [ "$i" -lt 30 ]; do
    out=$(sh "$MODDIR/control.sh" apply 2>&1)
    echo "$(date '+%m-%d %H:%M:%S') try $i: $out" >> "$LOG"
    case "$out" in
        OK*) break ;;
    esac
    sleep 2
    i=$((i + 1))
done

# Reflect the current state in module.prop so the manager list shows it.
sh "$MODDIR/control.sh" update_desc >/dev/null 2>&1

[ "$i" -lt 30 ] || echo "$(date '+%m-%d %H:%M:%S') giving up after $i tries" >> "$LOG"
exit 0
