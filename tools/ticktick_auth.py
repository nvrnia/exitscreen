"""One-time TickTick OAuth2, run in two steps.

    py tools/ticktick_auth.py                     step 1 - print the URL to open
    py tools/ticktick_auth.py "<redirected url>"  step 2 - swap the code for a token
    py tools/ticktick_auth.py --projects          list your lists, pick one

Two commands rather than an interactive prompt on purpose: no blocking on stdin,
and no local web server, which on Windows tends to raise a firewall dialog.

The access token is written into .env, which is gitignored. Nothing secret is
ever printed - the script reports lengths, not values.
"""

from __future__ import annotations

import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402

from exitscreen import config  # noqa: E402

AUTHORIZE_URL = "https://ticktick.com/oauth/authorize"
TOKEN_URL = "https://ticktick.com/oauth/token"
API = "https://api.ticktick.com/open/v1"

SCOPE = "tasks:read"  # read only - we never write back to TickTick
STATE = "exitscreen"


def step1_print_url():
    client_id = config.require("TICKTICK_CLIENT_ID")
    redirect = config.require("TICKTICK_REDIRECT_URI")

    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "scope": SCOPE,
            "state": STATE,
            "redirect_uri": redirect,
            "response_type": "code",
        }
    )
    print("\n1. Open this in your browser and click Allow:\n")
    print(f"   {AUTHORIZE_URL}?{query}\n")
    print("2. Your browser will fail to load a 127.0.0.1:8080 page. That is")
    print("   expected - nothing is listening there. Copy the whole URL out of")
    print("   the address bar.\n")
    print("3. Run this, with the URL in quotes:\n")
    print('   py tools/ticktick_auth.py "http://127.0.0.1:8080/?code=...&state=..."\n')


def step2_exchange(redirected: str):
    parsed = urllib.parse.urlparse(redirected)
    params = urllib.parse.parse_qs(parsed.query)

    code = (params.get("code") or [""])[0]
    if not code:
        raise SystemExit(
            "No ?code= found in that URL.\n"
            "Paste the whole address bar contents, in quotes, including the "
            "http://127.0.0.1:8080/ part."
        )

    client_id = config.require("TICKTICK_CLIENT_ID")
    client_secret = config.require("TICKTICK_CLIENT_SECRET")
    redirect = config.require("TICKTICK_REDIRECT_URI")

    payload = {
        "code": code,
        "grant_type": "authorization_code",
        "scope": SCOPE,
        "redirect_uri": redirect,
    }

    # TickTick's docs show the credentials as form fields, but several working
    # clients send them as HTTP Basic instead. Try form first, fall back to
    # Basic, and report which worked so the finding can be written down.
    attempts = [
        ("form fields", {**payload, "client_id": client_id,
                         "client_secret": client_secret}, None),
        ("HTTP Basic", payload, (client_id, client_secret)),
    ]

    for label, data, auth in attempts:
        response = requests.post(TOKEN_URL, data=data, auth=auth, timeout=30)
        print(f"  {label}: HTTP {response.status_code}")
        if not response.ok:
            continue
        try:
            blob = response.json()
        except ValueError:
            print(f"    response was not JSON: {response.text[:200]}")
            continue

        token = blob.get("access_token")
        if not token:
            print(f"    no access_token in response. Keys: {list(blob)}")
            continue

        config.update(TICKTICK_ACCESS_TOKEN=token)
        print(f"\n  authorised via {label}")
        print(f"  access_token: {len(token)} chars, written to .env")
        if blob.get("refresh_token"):
            config.update(TICKTICK_REFRESH_TOKEN=blob["refresh_token"])
            print("  refresh_token: also saved")
        else:
            print("  no refresh_token returned - re-run this if auth ever expires")
        if blob.get("expires_in"):
            days = int(blob["expires_in"]) / 86400
            print(f"  expires_in: {blob['expires_in']}s (~{days:.0f} days)")
        print("\nNext:  py tools/ticktick_auth.py --projects")
        return

    raise SystemExit(
        "\nBoth attempts failed. Codes are single-use and short-lived, so the "
        "most likely cause is a stale code - redo step 1 for a fresh one."
    )


def step3_list_projects():
    token = config.require("TICKTICK_ACCESS_TOKEN")
    response = requests.get(
        f"{API}/project",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    print(f"GET /project -> HTTP {response.status_code}")
    response.raise_for_status()

    projects = response.json()
    if not projects:
        raise SystemExit("No lists returned. Create a list in TickTick first.")

    print(f"\n{len(projects)} lists:\n")
    for p in projects:
        print(f"  {p.get('name')}")
        print(f"     id: {p.get('id')}")

    print("\nPick one and save its id:")
    print("  py -c \"import sys; sys.path.insert(0,'src');"
          " from exitscreen import config;"
          " config.update(TICKTICK_PROJECT_ID='PASTE_ID_HERE')\"")


def main():
    args = [a for a in sys.argv[1:] if a]

    if not args:
        step1_print_url()
    elif args[0] == "--projects":
        step3_list_projects()
    elif args[0].startswith("http"):
        step2_exchange(args[0])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
