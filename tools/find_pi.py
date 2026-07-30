"""Find the Pi on the local network.

    py tools/find_pi.py

More reliable than `ping exitscreen-pi.local`: mDNS name resolution frequently
fails on Windows even when the Pi is up, so a failed ping proves nothing. This
sweeps the subnet for hosts with SSH open and cross-checks the ARP table for
Raspberry Pi MAC prefixes, which is positive evidence either way.

Note the Pi 3 Model A+ has no Ethernet port - it is WiFi only - so if it never
appears here, WiFi credentials on the SD card are the first thing to check.
"""

from __future__ import annotations

import concurrent.futures as cf
import re
import socket
import subprocess
import sys

SSH_PORT = 22
TIMEOUT = 0.35

# Raspberry Pi Foundation / Raspberry Pi Ltd OUIs.
PI_OUIS = {
    "b8:27:eb": "Pi 1/2/3",
    "dc:a6:32": "Pi 4",
    "e4:5f:01": "Pi 4 / 400 / CM4",
    "2c:cf:67": "Pi 5",
    "28:cd:c1": "Pi Pico W",
}

HOSTNAMES = ["exitscreen-pi.local", "exitscreen-pi"]


def local_subnet() -> str | None:
    """The /24 prefix of the first private IPv4 address we hold."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.168.1.1", 1))  # no traffic sent, just picks a route
        ip = s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()
    return ip.rsplit(".", 1)[0]


def ssh_open(host: str) -> bool:
    s = socket.socket()
    s.settimeout(TIMEOUT)
    try:
        return s.connect_ex((host, SSH_PORT)) == 0
    except OSError:
        return False
    finally:
        s.close()


def arp_pi_entries() -> list[tuple[str, str, str]]:
    """(ip, mac, model) for any ARP entry with a Raspberry Pi MAC prefix."""
    try:
        out = subprocess.run(["arp", "-a"], capture_output=True, text=True,
                             timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return []

    found = []
    for line in out.splitlines():
        m = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F]{2}(?:[-:][0-9a-fA-F]{2}){5})",
                      line)
        if not m:
            continue
        ip, mac = m.group(1), m.group(2).lower().replace("-", ":")
        model = PI_OUIS.get(mac[:8])
        if model:
            found.append((ip, mac, model))
    return found


def main():
    print("1. hostname resolution")
    resolved = False
    for name in HOSTNAMES:
        try:
            ip = socket.gethostbyname(name)
            print(f"   {name} -> {ip}")
            resolved = True
        except OSError:
            print(f"   {name} -> no answer")
    if not resolved:
        print("   (mDNS often fails on Windows; this alone does not mean it is off)")

    prefix = local_subnet()
    if not prefix:
        print("\nno local IPv4 address found - is this machine on the network?")
        sys.exit(1)

    print(f"\n2. sweeping {prefix}.0/24 for SSH")
    hosts = [f"{prefix}.{i}" for i in range(1, 255)]
    with cf.ThreadPoolExecutor(max_workers=200) as ex:
        live = [h for h, ok in zip(hosts, ex.map(ssh_open, hosts)) if ok]

    for host in live:
        try:
            name = socket.gethostbyaddr(host)[0]
        except OSError:
            name = ""
        print(f"   {host}  ssh open  {name}")
    if not live:
        print("   nothing answering on port 22")

    print("\n3. Raspberry Pi MAC addresses seen")
    pis = arp_pi_entries()
    for ip, mac, model in pis:
        print(f"   {ip}  {mac}  ({model})")
    if not pis:
        print("   none")

    print()
    if pis:
        ip = pis[0][0]
        print(f"FOUND a Pi at {ip}. Connect with:")
        print(f"   ssh exitscreen@{ip}")
    elif live:
        print("SSH hosts exist but none has a Pi MAC. If one of the above is the")
        print("Pi, try it directly:  ssh exitscreen@<ip>")
    else:
        print("The Pi is NOT on this network. In order of likelihood:")
        print("  1. it is powered off")
        print("  2. WiFi credentials were never written to the SD card (the")
        print("     3 Model A+ has no Ethernet, so WiFi is the only route in)")
        print("  3. it is on a different network - e.g. a 5GHz-only SSID, which")
        print("     some Pi setups will not join")


if __name__ == "__main__":
    main()
