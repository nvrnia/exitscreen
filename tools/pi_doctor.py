"""Everything worth knowing about why the Pi keeps dying, in one run.

    ~/venv/bin/python tools/pi_doctor.py

Written because this has been diagnosed wrong twice - once as a dead SD card,
once as a loose one - when the evidence pointed at power both times. It gathers
the facts in one go rather than a command at a time over SSH.

The interesting part is the log analysis at the end: exitscreen.log has a line
every five minutes, so any gap in it is a period the Pi was not running. That
reconstructs the whole crash history even though journald is wiped on every boot.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

LOG = Path.home() / "exitscreen.log"
STAMP = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")

# From the firmware docs. The high bits are sticky - they stay set for the whole
# boot once it has happened, which is what makes them worth reading.
THROTTLE_BITS = {
    0: ("under-voltage RIGHT NOW", True),
    1: ("ARM frequency capped now", True),
    2: ("throttled now", True),
    3: ("soft temperature limit now", False),
    16: ("under-voltage HAS occurred this boot", True),
    17: ("ARM capping has occurred", False),
    18: ("throttling has occurred", False),
    19: ("soft temp limit has occurred", False),
}


def run(cmd: str) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=25)
        return (r.stdout + r.stderr).strip()
    except Exception as exc:  # noqa: BLE001
        return f"(could not run: {exc})"


def head(title: str) -> None:
    print(f"\n{'=' * 66}\n{title}\n{'=' * 66}")


def system() -> None:
    head("SYSTEM")
    model = Path("/proc/device-tree/model")
    print(f"  model      {model.read_text(errors='ignore').strip(chr(0)) if model.exists() else '?'}")
    print(f"  kernel     {run('uname -r')}")
    print(f"  now        {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  booted     {run('uptime -s')}")
    print(f"  uptime     {run('uptime -p')}")
    ntp = run("timedatectl show -p NTPSynchronized --value")
    print(f"  NTP synced {ntp}{'   <-- clock is NOT trustworthy' if ntp != 'yes' else ''}")


def power() -> None:
    head("POWER  (the standing suspect)")
    raw = run("vcgencmd get_throttled")
    print(f"  {raw}")
    m = re.search(r"0x([0-9a-fA-F]+)", raw)
    if not m:
        print("  could not read - is vcgencmd available?")
        return
    bits = int(m.group(1), 16)
    if bits == 0:
        print("  0x0 - no under-voltage or throttling recorded THIS BOOT.")
        print("  Note: these flags reset on every boot. A supply that browns out")
        print("  hard enough to kill the board may never live to record it.")
        return
    for bit, (label, serious) in THROTTLE_BITS.items():
        if bits & (1 << bit):
            print(f"  {'!! ' if serious else '   '}bit {bit:>2}: {label}")
    print(f"\n  temp       {run('vcgencmd measure_temp')}")
    print(f"  core volts {run('vcgencmd measure_volts core')}")


def storage() -> None:
    head("SD CARD AND FILESYSTEM")
    errs = run("dmesg | grep -iE 'mmc[0-9]|i/o error|EXT4-fs error|timeout' | tail -12")
    print(errs or "  no mmc or I/O errors in this boot's dmesg")
    orphan = run("dmesg | grep -i 'orphan cleanup'")
    print()
    if orphan:
        print("  !! orphan cleanup at boot - the LAST shutdown was UNCLEAN.")
        print("     The Pi lost power or hard-stopped rather than shutting down.")
    else:
        print("  no orphan cleanup - the last shutdown was clean")
    print(f"\n  disk  {run('df -h / | tail -1')}")
    print(f"  ro?   {run('findmnt -no OPTIONS / | cut -d, -f1')}")


def wifi() -> None:
    head("WIFI")
    print(f"  {run('iw dev wlan0 link') or run('iwconfig wlan0 2>/dev/null') or '  no wlan0'}")
    drops = run("dmesg | grep -iE 'wlan0|brcmfmac|deauth|disconnect' | tail -8")
    print(f"\n{drops or '  nothing in dmesg about wifi'}")


def journal() -> None:
    head("JOURNAL")
    storage_mode = run("journalctl --header 2>/dev/null | grep -i 'file path' | head -2")
    persistent = Path("/var/log/journal").is_dir()
    print(f"  persistent journal: {'YES' if persistent else 'NO'}")
    if not persistent:
        print("  Without this, every crash is invisible - the journal lives in RAM")
        print("  and is wiped on boot. Enable it and the next death leaves evidence:")
        print("    sudo mkdir -p /var/log/journal && sudo systemctl restart systemd-journald")
        return
    print("\n  last 15 lines of the PREVIOUS boot (what happened before it died):")
    prev = run("journalctl -b -1 -n 15 --no-pager 2>&1")
    print("   " + prev.replace("\n", "\n   "))


def deaths() -> None:
    """Reconstruct every outage from gaps in the log."""
    head("CRASH HISTORY  (reconstructed from gaps in exitscreen.log)")
    if not LOG.exists():
        print(f"  {LOG} not found")
        return

    times = []
    for line in LOG.read_text(errors="ignore").splitlines():
        m = STAMP.match(line)
        if m:
            try:
                times.append(datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"))
            except ValueError:
                pass
    if not times:
        print("  no timestamped lines")
        return

    print(f"  {len(times)} log entries, {times[0]:%d %b %H:%M} -> {times[-1]:%d %b %H:%M}\n")

    # cron runs every 5 min inside the window, so anything much longer is an
    # outage - except the expected overnight quiet period.
    gaps = []
    for a, b in zip(times, times[1:]):
        delta = b - a
        if delta > timedelta(minutes=20):
            overnight = a.hour >= 21 and b.hour <= 7 and delta < timedelta(hours=11)
            gaps.append((a, b, delta, overnight))

    unexpected = [g for g in gaps if not g[3]]
    if not unexpected:
        print("  no unexplained gaps - it has not missed a scheduled run")
    else:
        print(f"  {len(unexpected)} unexplained outage(s):\n")
        for a, b, delta, _ in unexpected[-12:]:
            hrs = delta.total_seconds() / 3600
            print(f"    died after {a:%a %d %b %H:%M}  ->  back {b:%a %d %b %H:%M}"
                  f"   ({hrs:.1f}h down)")

    boots = [line for line in LOG.read_text(errors="ignore").splitlines()
             if "waiting for NTP" in line]
    print(f"\n  {len(boots)} reboot(s) recorded (the @reboot job):")
    for line in boots[-8:]:
        print(f"    {line.strip()}")

    fails = [line for line in LOG.read_text(errors="ignore").splitlines()
             if "FAILED" in line]
    print(f"\n  {len(fails)} failure line(s):")
    for line in fails[-8:]:
        print(f"    {line.strip()}")


def main() -> int:
    print(f"exitscreen pi doctor — {datetime.now():%Y-%m-%d %H:%M:%S}")
    for section in (system, power, storage, wifi, journal, deaths):
        try:
            section()
        except Exception as exc:  # noqa: BLE001 - one bad section must not stop the sweep
            print(f"\n  ({section.__name__} failed: {exc.__class__.__name__}: {exc})")
    print("\n" + "=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
