#!/usr/bin/env python3
"""
Spotify OAuth setup helper for mywant.

One-time setup script to authorize Spotify and store the refresh token
persistently in the want's state (no config.yaml editing required).

Usage:
  1. Create a Spotify Developer App at https://developer.spotify.com/dashboard
  2. In the app settings, add this Redirect URI:
       http://127.0.0.1:8080/api/v1/oauth/callback
     (Spotify prohibits "localhost" — use 127.0.0.1 instead)
  3. Deploy the Spotify want with a fixed name, e.g.:
       mywant want deploy ~/.mywant/custom-types/mywant-spotify-plugin/spotify.yaml \
         --name my-spotify
  4. Run this script:
       SPOTIFY_CLIENT_ID=xxx SPOTIFY_CLIENT_SECRET=yyy \
         python3 oauth_helper.py --want-name my-spotify
  5. Authorize in the browser that opens.
  6. Done. The want will pick up the code automatically.

The refresh token is stored in the want's state (spotify_refresh_token field).
You still need SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in:
  ~/.mywant/config.yaml environments:
    SPOTIFY_CLIENT_ID: <your client id>
    SPOTIFY_CLIENT_SECRET: <your client secret>
"""

import argparse
import os
import sys
import urllib.parse

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SCOPES = "user-read-playback-state user-modify-playback-state user-read-currently-playing"
MYWANT_SERVER = os.environ.get("MYWANT_SERVER", "http://127.0.0.1:8080")
REDIRECT_URI = f"{MYWANT_SERVER}/api/v1/oauth/callback"


def main() -> None:
    parser = argparse.ArgumentParser(description="Spotify OAuth setup for mywant")
    parser.add_argument(
        "--want-name",
        default="my-spotify",
        help="Name of the deployed Spotify want (default: my-spotify)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Print the URL without opening a browser",
    )
    args = parser.parse_args()

    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        print("ERROR: Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET first.")
        print("  export SPOTIFY_CLIENT_ID=your_client_id")
        print("  export SPOTIFY_CLIENT_SECRET=your_client_secret")
        sys.exit(1)

    params = urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": args.want_name,
    })
    auth_url = f"{SPOTIFY_AUTH_URL}?{params}"

    print("=" * 62)
    print("  Spotify Authorization Setup for mywant")
    print("=" * 62)
    print(f"\n  Want name   : {args.want_name}")
    print(f"  Redirect URI: {REDIRECT_URI}")
    print()
    print("Steps:")
    print("  1. Open this URL in your browser:")
    print(f"\n     {auth_url}\n")
    print("  2. Log in to Spotify and authorize the app.")
    print("  3. Your browser will redirect to mywant and show")
    print("     'Authorization Successful'.")
    print(f"  4. The want '{args.want_name}' picks up the code on its")
    print("     next monitor tick (~5 sec) and stores the refresh token.")
    print()

    if not args.no_browser:
        try:
            import webbrowser
            webbrowser.open(auth_url)
            print("  (Browser opened automatically.)")
        except Exception:
            print("  (Open the URL above manually.)")


if __name__ == "__main__":
    main()
