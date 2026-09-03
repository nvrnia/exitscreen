#!/usr/bin/env bash
# Push the working tree to an already-set-up Pi. setup_pi.sh does the one-time
# machine setup; this is the one you run every time after that.
#
#   deploy/push.sh                          # default host
#   deploy/push.sh exitscreen@192.168.0.112 # or name one
#   deploy/push.sh --watchdog               # also install the wifi watchdog
#
# Safe to re-run.

set -euo pipefail

HOST="exitscreen@exitscreen-pi.local"
WATCHDOG=0
for arg in "$@"; do
    case "$arg" in
        --watchdog) WATCHDOG=1 ;;
        *) HOST="$arg" ;;
    esac
done

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

REMOTE="exitscreen"
PY="\$HOME/venv/bin/python"

# Two files the app cannot run without and git will never carry: the TickTick
# token, and the settings that say which stop and which timetable. Checking
# first, because deploying code that needs them onto a Pi that lacks them stops
# the panel until someone notices.
echo "==> 1/6  checking what git does not carry"
missing=0
for f in .env assets/settings.json; do
    if [ -f "$f" ]; then
        echo "    $f"
    else
        echo "    MISSING $f"
        missing=1
    fi
done
if [ ! -f assets/timetable.json ]; then
    echo "    MISSING assets/timetable.json - the commute column will be absent."
    echo "             build it with: py tools/build_bus_timetable.py path/to/gtfs-nl.zip"
fi
[ "$missing" -eq 0 ] || { echo "    stopping, nothing has been touched"; exit 1; }

echo "==> 2/6  code"
ssh "$HOST" "mkdir -p ~/$REMOTE/assets"
scp -q -r src tools run.py requirements.txt deploy "$HOST:~/$REMOTE/"

echo "==> 3/6  assets, including the gitignored ones"
scp -q -r assets/fonts assets/licences "$HOST:~/$REMOTE/assets/" 2>/dev/null || true
scp -q assets/*.json "$HOST:~/$REMOTE/assets/"
scp -q .env "$HOST:~/$REMOTE/.env"

# A shell script that has been through a Windows checkout can arrive with CRLF
# endings, and a #! line ending in \r fails with "bad interpreter". This is the
# same thing that mangled every cron line on 2026-08-23.
ssh "$HOST" "sed -i 's/\r\$//' ~/$REMOTE/deploy/*.sh && chmod +x ~/$REMOTE/deploy/*.sh"

# The bus timetable used to be called bus40.json. Leaving the old one behind is
# harmless but confusing, and nothing reads it now.
ssh "$HOST" "rm -f ~/$REMOTE/assets/bus40.json"

echo "==> 4/6  cron"
ssh "$HOST" "tr -d '\r' < ~/$REMOTE/deploy/crontab | crontab - && crontab -l | grep -c run.py | xargs -I{} echo '    {} run.py entries installed'"

echo "==> 5/6  wifi watchdog"
if [ "$WATCHDOG" -eq 1 ]; then
    # Root's crontab, not the exitscreen user's: it bounces the interface and
    # can reboot. Non-fatal, since it needs sudo and may prompt.
    if ssh -t "$HOST" "sudo cp ~/$REMOTE/deploy/wifi_watchdog.sh /usr/local/bin/ \
        && sudo chmod +x /usr/local/bin/wifi_watchdog.sh \
        && (sudo crontab -l 2>/dev/null | grep -v wifi_watchdog; \
            echo '*/5 * * * * /usr/local/bin/wifi_watchdog.sh') | sudo crontab -"; then
        echo "    installed in root's crontab"
    else
        echo "    could not install it (sudo). Do it by hand, see BACKLOG.md"
    fi
else
    echo "    skipped, pass --watchdog to install it"
fi

echo "==> 6/6  checking it runs"
ssh "$HOST" "cd ~/$REMOTE && $PY run.py --dry-run"

cat <<DONE

Deployed to $HOST.

Cron will pick it up within five minutes. To draw it now:
  ssh $HOST '~/venv/bin/python ~/exitscreen/run.py --force'
DONE
