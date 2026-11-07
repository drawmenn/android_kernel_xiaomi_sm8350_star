#!/system/bin/sh
# Command backend for the WebUI and the boot service.
#   control.sh init             seed the config with defaults
#   control.sh status           state, config, live kernel rules
#   control.sh apps             installed user apps (pkg uid lines)
#   control.sh save <base64>    replace the config (base64 payload)
#   control.sh apply            resolve target UIDs and write kernel rules
#   control.sh log              tail of the apply log
#   control.sh update_desc      reflect live status into module.prop
#
# Config format: one or more "target=<pkg>" lines (apps the rules apply
# to) and any number of "pkg=<pkg>" lines. Every target x package pair
# becomes one kernel rule; the kernel table holds 256 entries.
#
# Output contract: first line "OK" on success, "ERR: <reason>" on failure.
# apply additionally reads the kernel table back and only reports OK when
# every rule really landed.

MODDIR=$(cd "$(dirname "$0")" && pwd)
STORE=/data/adb/uid_path_filter_rules
CONFIG="$STORE/config"
LOG="$STORE/apply.log"
CFG=/sys/kernel/uid_path_filter/config
SLOTS=256
VERSION=v4.0

[ "$(id -u)" = 0 ] || { echo "ERR: root required"; exit 1; }
mkdir -p "$STORE"

log() { echo "$(date '+%m-%d %H:%M:%S') $1" >> "$LOG"; }

ensure_allow() {
    [ -e "$CFG" ] || return 1
    [ -w "$CFG" ] && return 0
    [ -f "$MODDIR/magiskpolicy" ] || return 1
    [ -x "$MODDIR/magiskpolicy" ] || chmod 0755 "$MODDIR/magiskpolicy" 2>/dev/null
    [ -x "$MODDIR/magiskpolicy" ] || return 1
    # Grant the sysfs node to the calling domain plus the two common
    # root domains, so both the WebUI shell and the boot service can
    # reach it under enforcing SELinux.
    dom=$(cat /proc/self/attr/current 2>/dev/null | cut -d: -f2)
    for d in "$dom" ksu magisk; do
        [ -n "$d" ] || continue
        "$MODDIR/magiskpolicy" --live \
            "allow $d sysfs file { read write open getattr }" >/dev/null 2>&1
    done
    [ -w "$CFG" ]
}

resolve_uid() {
    pm list packages -U "$1" 2>/dev/null | sed -n 's/.*uid:\([0-9]*\).*/\1/p' | head -n 1
}

valid_pkg() {
    case "$1" in
        ""|*[!A-Za-z0-9._]*) return 1 ;;
    esac
    return 0
}

cmd_init() {
    if [ ! -f "$CONFIG" ]; then
        cat > "$CONFIG" <<'EOF'
target=com.chunqiunativecheck
pkg=com.omarea.vtools
pkg=com.sevtinge.hyperceiler
pkg=io.github.a13e300.ksuwebui
pkg=top.hookvip.pro
EOF
        chmod 600 "$CONFIG"
    fi
    echo "OK"
}

cmd_status() {
    if [ -e "$CFG" ]; then s=1; else s=0; fi
    if [ "$s" = 1 ] && ensure_allow; then w=1; else w=0; fi
    echo "OK"
    echo "module=$VERSION"
    echo "kernel=$(uname -r 2>/dev/null)"
    echo "sysfs=$s"
    echo "writable=$w"
    if [ -f "$CONFIG" ]; then
        cat "$CONFIG"
        sed -n 's/^target=//p' "$CONFIG" | while IFS= read -r t; do
            uid=$(resolve_uid "$t")
            echo "uidmap $t ${uid:-none}"
        done
    fi
    if [ "$w" = 1 ]; then
        echo "---rules"
        cat "$CFG"
        echo "---end"
    fi
}

cmd_apps() {
    echo "OK"
    pm list packages -3 -U 2>/dev/null | sed -n 's/^package:\([^ ]*\) uid:\([0-9]*\)$/\1 \2/p'
}

cmd_log() {
    echo "OK"
    tail -n 60 "$LOG" 2>/dev/null
}

cmd_save() {
    tmp="$STORE/config.new"
    echo "${1:-}" | base64 -d > "$tmp" 2>/dev/null || { echo "ERR: bad payload"; exit 1; }
    nt=0
    np=0
    while IFS= read -r line; do
        case "$line" in
            "") ;;
            target=*)
                t=${line#target=}
                valid_pkg "$t" || { rm -f "$tmp"; echo "ERR: bad target: $t"; exit 1; }
                nt=$((nt + 1))
                ;;
            pkg=*)
                p=${line#pkg=}
                valid_pkg "$p" || { rm -f "$tmp"; echo "ERR: bad pkg: $p"; exit 1; }
                np=$((np + 1))
                ;;
            *)
                rm -f "$tmp"
                echo "ERR: bad line: $line"
                exit 1
                ;;
        esac
    done < "$tmp"
    if [ "$nt" -lt 1 ]; then
        rm -f "$tmp"
        echo "ERR: at least one target is required"
        exit 1
    fi
    if [ $((nt * np)) -gt "$SLOTS" ]; then
        rm -f "$tmp"
        echo "ERR: too many rules ($((nt * np)) > $SLOTS kernel slots)"
        exit 1
    fi
    chmod 600 "$tmp"
    mv -f "$tmp" "$CONFIG"
    echo "OK"
    echo "saved targets=$nt pkgs=$np"
}

cmd_update_desc() {
    [ -f "$MODDIR/module.prop" ] || return
    if ! [ -e "$CFG" ]; then
        d="✗ kernel module missing (flash r6 kernel)"
    elif ! ensure_allow; then
        d="✗ sysfs not writable (SELinux)"
    else
        cnt=$(grep -c . "$CFG" 2>/dev/null)
        cnt=${cnt:-0}
        if [ "$cnt" -gt 0 ]; then
            d="✓ $cnt rules active"
        else
            d="⚠ no rules applied"
        fi
    fi
    sed -i "s/^description=.*/description=$d/" "$MODDIR/module.prop" 2>/dev/null
}

cmd_apply() {
    [ -f "$CONFIG" ] || cmd_init >/dev/null

    if ! ensure_allow; then
        echo "ERR: sysfs not writable (node exists: $( [ -e "$CFG" ] && echo yes || echo no ))"
        log "apply: sysfs not writable (node exists: $( [ -e "$CFG" ] && echo yes || echo no ))"
        exit 1
    fi

    nt=$(sed -n 's/^target=//p' "$CONFIG" | grep -c .)
    np=$(sed -n 's/^pkg=//p' "$CONFIG" | grep -c .)
    if [ "$nt" -lt 1 ]; then
        echo "ERR: no target in config"
        log "apply: no target in config"
        exit 1
    fi
    if [ $((nt * np)) -gt "$SLOTS" ]; then
        echo "ERR: too many rules ($((nt * np)) > $SLOTS kernel slots)"
        log "apply: too many rules"
        exit 1
    fi

    echo "clear" > "$CFG" 2>/dev/null || {
        echo "ERR: cannot clear kernel table"
        log "apply: clear failed"
        exit 1
    }

    n=0
    f=0
    attempted=0
    skipped=""
    for t in $(sed -n 's/^target=//p' "$CONFIG"); do
        uid=$(resolve_uid "$t")
        if [ -z "$uid" ]; then
            skipped="$skipped $t"
            log "apply: skip target (no uid): $t"
            continue
        fi
        for p in $(sed -n 's/^pkg=//p' "$CONFIG"); do
            valid_pkg "$p" || continue
            attempted=$((attempted + 1))
            if echo "add $uid /Android/data/$p" > "$CFG" 2>/dev/null; then
                n=$((n + 1))
            else
                f=$((f + 1))
                log "apply: write failed: uid=$uid pkg=$p"
            fi
        done
    done

    if [ "$attempted" -eq 0 ]; then
        echo "ERR: no rules written (target apps not installed?)"
        log "apply: no rules written, skipped:$skipped"
        exit 1
    fi

    got=$(grep -c . "$CFG" 2>/dev/null)
    got=${got:-0}
    if [ "$f" -gt 0 ] || [ "$got" -ne "$n" ]; then
        echo "ERR: applied $n/$attempted, kernel table has $got"
        log "apply FAILED: $n/$attempted ok, table=$got, skipped:$skipped"
        exit 1
    fi

    echo "OK"
    echo "applied=$n"
    echo "targets=$nt"
    echo "pkgs=$np"
    [ -z "$skipped" ] || echo "skipped:$skipped"
    log "apply ok: verified $n rules in kernel table ($nt targets x $np pkgs)${skipped:+, skipped:$skipped}"
    if [ -f "$MODDIR/module.prop" ]; then
        sed -i "s/^description=.*/description=✓ $n rules active/" "$MODDIR/module.prop" 2>/dev/null
    fi
}

case "${1:-}" in
    init)        cmd_init ;;
    status)      cmd_status ;;
    apps)        cmd_apps ;;
    log)         cmd_log ;;
    save)        cmd_save "${2:-}" ;;
    apply)       cmd_apply ;;
    update_desc) cmd_update_desc ;;
    *)           echo "ERR: usage: control.sh init|status|apps|log|save <b64>|apply|update_desc"; exit 1 ;;
esac
