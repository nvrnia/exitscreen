#!/usr/bin/env bash
# Notice when the wifi has silently died, and kick it.
#
#   sudo cp deploy/wifi_watchdog.sh /usr/local/bin/
#   sudo chmod +x /usr/local/bin/wifi_watchdog.sh
#   sudo crontab -e     # then add:
#   */5 * * * * /usr/local/bin/wifi_watchdog.sh
#
# Must run as root: bouncing an interface needs it. Note that is ROOT's crontab,
# not the exitscreen user's.
#
# Why this is needed at all: the failure is not a clean disconnect. The Broadcom
# radio stays *nominally associated* while passing no traffic, so NetworkManager
# sees "connected" and has no reason to retry. On 22 August the Pi sat like that
# for eleven hours and only came back when the power was pulled.
#
# Deliberately pings the ROUTER, not the internet. A router that answers while
# the internet is down is a broken uplink, which bouncing our wifi cannot fix -
# and pointless reconnects are their own risk.

set -uo pipefail

STATE=/run/wifi_watchdog.fails     # /run is tmpfs: no SD card writes
IFACE=wlan0
MAX_FAILS=6                        # ~30 min at a 5-minute cadence, then reboot

log() { logger -t wifi-watchdog "$*"; echo "$(date '+%F %T')  $*"; }

gateway="$(ip route | awk '/^default/ {print $3; exit}')"
if [ -z "$gateway" ]; then
    log "no default route - treating as a failure"
else
    # Two pings, 3s timeout. One dropped packet on a -70dBm link is normal.
    if ping -c 2 -W 3 "$gateway" >/dev/null 2>&1; then
        [ -f "$STATE" ] && { log "back after $(cat "$STATE") failure(s)"; rm -f "$STATE"; }
        exit 0
    fi
fi

fails=$(( $( [ -f "$STATE" ] && cat "$STATE" || echo 0 ) + 1 ))
echo "$fails" > "$STATE"
log "cannot reach gateway ${gateway:-unknown} (failure $fails)"

if [ "$fails" -ge "$MAX_FAILS" ]; then
    # Bouncing has not helped for half an hour. A reboot rebuilds the interface
    # from scratch, which is what pulling the power was doing by hand.
    log "still down after $fails tries - rebooting"
    rm -f "$STATE"
    /sbin/reboot
    exit 0
fi

log "bouncing $IFACE"
nmcli device disconnect "$IFACE" >/dev/null 2>&1
sleep 5
nmcli device connect "$IFACE" >/dev/null 2>&1
sleep 10

if ping -c 2 -W 3 "$gateway" >/dev/null 2>&1; then
    log "recovered after bouncing $IFACE"
    rm -f "$STATE"
else
    log "bounce did not help; will try again next run"
fi
