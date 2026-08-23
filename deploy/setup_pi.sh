#!/usr/bin/env bash
# Set up a fresh Raspberry Pi for exitscreen, in one run.
#
#   scp deploy/setup_pi.sh exitscreen@exitscreen-pi.local:~/
#   ssh exitscreen@exitscreen-pi.local "bash ~/setup_pi.sh"
#
# Everything below was learned the hard way on Raspbian 13 (trixie) — see the
# "First light" notes in BACKLOG.md. The comments explain the non-obvious
# choices, because several of them contradict the driver's own README.
#
# Safe to re-run: every step is idempotent.

set -euo pipefail

VENV="$HOME/venv"
DRIVER="$HOME/IT8951"
PROJECT="$HOME/exitscreen"

echo "==> 1/6  system packages"
sudo apt-get update
# python3-pil, NOT python3-pillow — Debian uses the historical name and the
# other has no candidate at all.
# Deliberately absent: python3-rpi.gpio. Trixie preinstalls python3-rpi-lgpio,
# which provides the RPi.GPIO module name on the modern kernel interface.
# Installing the legacy package would shadow the working one.
sudo apt-get install -y \
    python3-pil \
    python3-dev \
    python3-setuptools \
    python3-wheel \
    python3-requests \
    python3-venv \
    cython3 \
    git

echo "==> 2/6  checking SPI"
if [ -e /dev/spidev0.0 ]; then
    echo "    /dev/spidev0.0 present"
else
    echo "    SPI is off. Enabling via raspi-config (a reboot will be needed)."
    sudo raspi-config nonint do_spi 0
    echo "    RUN THIS SCRIPT AGAIN AFTER REBOOTING."
fi

echo "==> 3/6  group membership"
for group in spi gpio; do
    if id -nG "$USER" | grep -qw "$group"; then
        echo "    already in $group"
    else
        sudo usermod -aG "$group" "$USER"
        echo "    added to $group — log out and back in for it to take effect"
    fi
done

echo "==> 4/6  IT8951 driver"
if [ -d "$DRIVER" ]; then
    git -C "$DRIVER" pull --ff-only || true
else
    git clone https://github.com/GregDMeyer/IT8951.git "$DRIVER"
fi

# --system-site-packages so the venv can see apt's prebuilt Pillow, requests and
# GPIO rather than rebuilding them. On a 512MB board, compiling Pillow from
# source is a real risk of failure, not just a slow build.
[ -d "$VENV" ] || python3 -m venv --system-site-packages "$VENV"

# No [rpi] extra: it would pull the legacy RPi.GPIO from PyPI and shadow
# rpi-lgpio. --no-build-isolation makes pip use apt's Cython instead of
# downloading and compiling its own, since armhf often has no prebuilt wheel.
"$VENV/bin/pip" install --no-build-isolation "$DRIVER"

echo "==> 5/6  verifying"
"$VENV/bin/python" - <<'PY'
from IT8951.display import AutoEPDDisplay  # noqa: F401
from IT8951 import constants
from PIL import __version__ as pillow_version
modes = [m for m in dir(constants.DisplayModes) if not m.startswith("_")]
print(f"    IT8951 OK | Pillow {pillow_version} | modes: {', '.join(modes)}")
PY

echo "==> 6/6  cron"
if [ -f "$PROJECT/deploy/crontab" ]; then
    # `set -o pipefail` plus `set -e` made this silently abort the script on a
    # fresh machine: with no crontab yet, `crontab -l` exits non-zero AND
    # `grep -v` finds nothing to print, which is also non-zero. Both are normal
    # here, so the pipeline is guarded rather than treated as failure.
    # deploy/crontab is the whole schedule, so install it outright. The old
    # version tried to merge, filtering with `grep -v 'exitscreen/run.py'` -
    # which never matched, because the lines read "cd .../exitscreen && ...
    # run.py". Every run appended another duplicate copy.
    #
    # tr -d '\r' matters for a file that has been through a Windows checkout:
    # a cron line ending in  is silently mangled.
    tr -d '\r' < "$PROJECT/deploy/crontab" | crontab -
    echo "    installed from $PROJECT/deploy/crontab"
else
    echo "    $PROJECT not deployed yet — copy the project across, then re-run"
fi

cat <<'DONE'

Done. Still to do by hand:
  1. copy the project over:
       scp -r src tools assets run.py deploy .env exitscreen@<pi>:~/exitscreen/
  2. .env is gitignored and does NOT travel with the code. Either copy it from
     the laptop or re-run tools/ticktick_auth.py to mint a fresh token.
  3. first light:
       ~/venv/bin/python ~/exitscreen/run.py --force
DONE
