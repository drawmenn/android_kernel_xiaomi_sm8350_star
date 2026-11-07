#!/system/bin/sh
MODDIR=${0%/*}

# BakaSU installs every file 0644; restore exec bits before first run.
chmod 0755 "$MODDIR/magiskpolicy" 2>/dev/null
chmod 0755 "$MODDIR/control.sh"   2>/dev/null
chmod 0755 "$MODDIR/service.sh"   2>/dev/null

sh "$MODDIR/control.sh" init >/dev/null 2>&1

ui_print "- UID Path Filter Rules v4.0 installed"
ui_print "- Reboot once, then manage rules from the module WebUI"
