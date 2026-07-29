#!/usr/bin/env python3
"""
Spotify now-playing monitor + playback controller.

Called by monitor_mrs_agent on each polling tick. Receives a JSON argument:
  {"action":"","oauth_code":"","rate_limit_until":"","last_state_poll_at":"",
   "want_name":""}

"want_name" is the engine-provided %{want_name} — used as the OAuth `state` so
the callback can find this want regardless of what it was named.

Tokens are stored in ~/.mywant/secrets/spotify_tokens.json (NOT in args/logs).
Credentials come from environment variables:
  SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
"""

import base64
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

TOKENS_FILE = os.path.expanduser("~/.mywant/secrets/spotify_tokens.json")

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = None


def progress(pct: int, msg: str = "") -> None:
    print(json.dumps({"_progress": pct, "_message": msg}, ensure_ascii=False), flush=True)


def load_tokens() -> tuple:
    """Return (access_token, token_expiry, refresh_token) from secrets file."""
    try:
        with open(TOKENS_FILE) as f:
            d = json.load(f)
        return d.get("access_token", ""), d.get("token_expiry", ""), d.get("refresh_token", "")
    except (FileNotFoundError, json.JSONDecodeError):
        return "", "", ""


def save_tokens(access_token: str, token_expiry: str, refresh_token: str) -> None:
    """Persist tokens to secrets file (chmod 600)."""
    os.makedirs(os.path.dirname(TOKENS_FILE), exist_ok=True)
    with open(TOKENS_FILE, "w") as f:
        json.dump({"access_token": access_token, "token_expiry": token_expiry,
                   "refresh_token": refresh_token}, f, indent=2)
    os.chmod(TOKENS_FILE, 0o600)


def get_credentials():
    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
    return client_id, client_secret


def is_token_valid(access_token: str, token_expiry: str) -> bool:
    if not access_token or not token_expiry:
        return False
    try:
        expiry = datetime.fromisoformat(token_expiry.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) < expiry
    except Exception:
        return False


def exchange_code(client_id: str, client_secret: str, code: str, redirect_uri: str) -> tuple:
    """Exchange an authorization code for access_token + refresh_token."""
    mywant_server = os.environ.get("MYWANT_SERVER", "http://localhost:8080")
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri or f"{mywant_server}/api/v1/oauth/callback",
    }).encode()
    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=data,
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    resp = urllib.request.urlopen(req, timeout=10, context=_SSL_CTX)
    body = json.loads(resp.read().decode())
    access = body["access_token"]
    new_refresh = body.get("refresh_token", "")
    expires_in = int(body.get("expires_in", 3600))
    expiry_ts = datetime.now(timezone.utc).timestamp() + expires_in - 60
    expiry_str = datetime.fromtimestamp(expiry_ts, timezone.utc).isoformat()
    return access, expiry_str, new_refresh


def refresh_token(client_id: str, client_secret: str, refresh_token_val: str):
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token_val,
    }).encode()
    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=data,
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    resp = urllib.request.urlopen(req, timeout=10, context=_SSL_CTX)
    body = json.loads(resp.read().decode())
    token = body["access_token"]
    expires_in = int(body.get("expires_in", 3600))
    expiry_ts = datetime.now(timezone.utc).timestamp() + expires_in - 60
    expiry_str = datetime.fromtimestamp(expiry_ts, timezone.utc).isoformat()
    return token, expiry_str


def spotify_api(method: str, path: str, access_token: str, body=None) -> tuple:
    """Returns (status_code, response_dict_or_None)."""
    url = f"https://api.spotify.com/v1{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {access_token}",
                 "Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=8, context=_SSL_CTX)
        status = resp.status
        raw = resp.read().strip()
        if raw:
            try:
                return status, json.loads(raw.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                return status, None
        return status, None
    except urllib.error.HTTPError as e:
        retry_after = None
        if e.headers:
            val = e.headers.get("Retry-After")
            if val and val.isdigit():
                retry_after = int(val)
        return e.code, {"retry_after": retry_after or 30}


def execute_action(action: str, token: str) -> str:
    """Executes a playback action against the Spotify Web API.
    Returns an error message on failure, or "" on success/no-op."""
    if not action:
        return ""
    if action == "play":
        status, _ = spotify_api("PUT", "/me/player/play", token)
        if status == 404:
            # Spotify requires an already-active/visible device to target — it
            # won't "wake up" playback out of thin air. Fall back to the first
            # available device (e.g. a phone/desktop app that's open but idle).
            _, ddata = spotify_api("GET", "/me/player/devices", token)
            devices = (ddata or {}).get("devices") or []
            if not devices:
                return "No available Spotify device found — open Spotify on a device first."
            device = devices[0]
            status2, _ = spotify_api("PUT", "/me/player/play", token, {"device_id": device.get("id")})
            if status2 not in (200, 202, 204):
                return f"Failed to start playback on {device.get('name') or 'device'} (status {status2})."
            return ""
        if status not in (200, 202, 204):
            return f"Play failed (status {status})."
        return ""
    elif action == "pause":
        spotify_api("PUT", "/me/player/pause", token)
    elif action == "next":
        spotify_api("POST", "/me/player/next", token)
    elif action == "previous":
        spotify_api("POST", "/me/player/previous", token)
    elif action.startswith("volume:"):
        try:
            pct = int(action.split(":", 1)[1])
            pct = max(0, min(100, pct))
            spotify_api("PUT", f"/me/player/volume?volume_percent={pct}", token)
        except ValueError:
            pass
    return ""


def build_oauth_url(client_id: str, want_name: str) -> str:
    """Authorization URL for the card's "Connect to Spotify" button.

    The OAuth `state` carries the want name so /api/v1/oauth/callback can find
    the want to hand the authorization code back to. The name arrives from the
    engine as %{want_name} in the arg template, so the button works whatever
    the want is called.
    """
    if not client_id or not want_name:
        return ""
    mywant_server = os.environ.get("MYWANT_SERVER", "http://127.0.0.1:8080")
    redirect_uri = urllib.parse.quote(f"{mywant_server}/api/v1/oauth/callback", safe="")
    scope = urllib.parse.quote("user-read-playback-state user-modify-playback-state user-read-currently-playing", safe="")
    state = urllib.parse.quote(want_name, safe="")
    return (
        f"https://accounts.spotify.com/authorize"
        f"?client_id={client_id}&response_type=code"
        f"&redirect_uri={redirect_uri}&scope={scope}&state={state}"
    )


def empty_result(error: str = "", oauth_url: str = "") -> dict:
    return {
        "oauth_url": oauth_url,
        "webhook_payload": None,
        "track_name": "",
        "artist_name": "",
        "album_name": "",
        "album_art_url": "",
        "is_playing": False,
        "progress_ms": 0,
        "duration_ms": 0,
        "device_name": "",
        "volume_percent": 0,
        "last_error": error,
    }


STATE_POLL_INTERVAL_MS = 5000  # fetch Spotify playback state at most once per 5s


def main() -> None:
    arg = {}
    if len(sys.argv) > 1:
        try:
            arg = json.loads(sys.argv[1])
        except json.JSONDecodeError:
            pass

    def clean(val: str) -> str:
        v = val.strip()
        return "" if (v.startswith("%{") and v.endswith("}")) else v

    # Only non-sensitive fields come via args now
    action           = clean(arg.get("action", ""))
    oauth_code       = clean(arg.get("oauth_code", ""))
    rate_limit_until = clean(arg.get("rate_limit_until", ""))
    want_name        = clean(arg.get("want_name", ""))
    last_state_poll_at = float(clean(arg.get("last_state_poll_at", "")) or "0")
    now_ms = time.time() * 1000
    state_poll_due = (now_ms - last_state_poll_at) >= STATE_POLL_INTERVAL_MS

    # Tokens come from file, not args
    current_token, current_expiry, refresh_tok = load_tokens()
    # Fallback to env var if file has no refresh token (first run)
    if not refresh_tok:
        refresh_tok = os.environ.get("SPOTIFY_REFRESH_TOKEN", "").strip()

    client_id, client_secret = get_credentials()

    if not client_id or not client_secret:
        result = empty_result(
            "Missing Spotify credentials. "
            "Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET "
            "in ~/.mywant/config.yaml environments."
        )
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return

    # Fast path: nothing to do
    if not action and not oauth_code and not state_poll_due:
        print(json.dumps({"last_state_poll_at": str(last_state_poll_at)}, ensure_ascii=False), flush=True)
        return

    # OAuth code exchange
    consumed_oauth_code = False
    if oauth_code:
        progress(10, "exchanging OAuth authorization code")
        mywant_server = os.environ.get("MYWANT_SERVER", "http://127.0.0.1:8080")
        redirect_uri = f"{mywant_server}/api/v1/oauth/callback"
        try:
            current_token, current_expiry, refresh_tok = exchange_code(
                client_id, client_secret, oauth_code, redirect_uri
            )
            save_tokens(current_token, current_expiry, refresh_tok)
            consumed_oauth_code = True
        except Exception as e:
            result = empty_result(f"OAuth code exchange failed: {e}")
            result["oauth_code"] = ""
            print(json.dumps(result, ensure_ascii=False), flush=True)
            return

    if not refresh_tok:
        result = empty_result(
            "Spotify authorization required. Click the button below to connect.",
            build_oauth_url(client_id, want_name),
        )
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return

    # Refresh access token if expired or missing
    new_token  = current_token
    new_expiry = current_expiry

    if not is_token_valid(current_token, current_expiry):
        progress(20, "refreshing access token")
        try:
            new_token, new_expiry = refresh_token(client_id, client_secret, refresh_tok)
            save_tokens(new_token, new_expiry, refresh_tok)
        except Exception as e:
            result = empty_result(f"Token refresh failed: {e}")
            print(json.dumps(result, ensure_ascii=False), flush=True)
            return

    # Execute pending action
    executed_action = False
    action_error = ""
    if action:
        progress(40, f"action: {action}")
        action_error = execute_action(action, new_token)
        time.sleep(0.1)
        executed_action = True

    # Rate-limit backoff
    if rate_limit_until and not action:
        try:
            until_dt = datetime.fromisoformat(rate_limit_until.replace("Z", "+00:00"))
            remaining = int((until_dt - datetime.now(timezone.utc)).total_seconds())
            if remaining > 0:
                result = {"last_error": f"Rate limited by Spotify ({remaining}s remaining)"}
                print(json.dumps(result, ensure_ascii=False), flush=True)
                return
        except Exception:
            pass

    # Fetch playback state
    progress(70, "fetching playback state")
    status, data = spotify_api("GET", "/me/player", new_token)

    if status == 429:
        from datetime import timedelta
        retry_after = (data or {}).get("retry_after", 30)
        until_dt = datetime.now(timezone.utc) + timedelta(seconds=retry_after)
        until_local = datetime.fromtimestamp(until_dt.timestamp()).strftime('%H:%M:%S')
        result = {
            "rate_limit_until": until_dt.isoformat(),
            "last_error": f"Rate limited by Spotify (until {until_local})",
        }
        if executed_action:
            result["spotify_action"] = ""
        if consumed_oauth_code:
            result["oauth_code"] = ""
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return

    if status == 401:
        progress(75, "token expired, refreshing")
        try:
            new_token, new_expiry = refresh_token(client_id, client_secret, refresh_tok)
            save_tokens(new_token, new_expiry, refresh_tok)
            status, data = spotify_api("GET", "/me/player", new_token)
        except Exception as e:
            result = empty_result(f"Token refresh on 401: {e}")
            print(json.dumps(result, ensure_ascii=False), flush=True)
            return

    result = empty_result()
    result["last_state_poll_at"] = str(int(time.time() * 1000))

    if rate_limit_until:
        result["rate_limit_until"] = ""
    if executed_action:
        result["spotify_action"] = ""
    if consumed_oauth_code:
        result["oauth_code"] = ""

    if status == 200 and data:
        item = data.get("item") or {}
        if item:
            result["track_name"]   = item.get("name", "")
            artists = item.get("artists") or []
            result["artist_name"]  = ", ".join(a.get("name", "") for a in artists)
            album = item.get("album") or {}
            result["album_name"]   = album.get("name", "")
            images = album.get("images") or []
            if images:
                result["album_art_url"] = images[0].get("url", "")
            result["duration_ms"]  = item.get("duration_ms", 0)
        result["is_playing"]   = data.get("is_playing", False)
        result["progress_ms"]  = data.get("progress_ms", 0)
        device = data.get("device") or {}
        result["device_name"]    = device.get("name", "")
        result["volume_percent"] = device.get("volume_percent", 0)
    elif status == 204:
        result["last_error"] = ""
    elif status and status != 200:
        result["last_error"] = f"Spotify API returned {status}"

    # A failed play/pause/next/previous/volume action takes priority over
    # whatever the immediately-following state poll reports (a device that
    # just failed to start playback correctly shows up as 204/"nothing
    # playing" otherwise, silently masking the real cause).
    if action_error:
        result["last_error"] = action_error

    progress(100, result.get("track_name") or "no playback")
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
