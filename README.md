# mywant-spotify-plugin

A MyWant want type that shows the track currently playing on Spotify — title,
artist, album artwork, progress — and lets you control playback (play / pause /
next / previous / volume) from the want card.

Playback state is polled through the Spotify Web API about once every 5 seconds.
Actions are picked up faster: the card writes to the want's `spotify_action`
state field and the monitor checks it every 300 ms.

No credential is stored in this repository. The client ID and secret come from
the environment, and OAuth tokens are written to
`~/.mywant/secrets/spotify_tokens.json` (chmod 600) — never into want state,
script arguments, or logs.

## Install

```sh
mywant custom install onelittlenightmusic/mywant-spotify-plugin
```

Then restart the server so the want type and its agent are registered.

## Setup

1. Create a Spotify app at https://developer.spotify.com/dashboard and add this
   Redirect URI:

   ```
   http://127.0.0.1:8080/api/v1/oauth/callback
   ```

   Spotify rejects `localhost`, so `127.0.0.1` is required.

2. Put the credentials in `~/.mywant/config.yaml` under `environments`:

   ```yaml
   environments:
     SPOTIFY_CLIENT_ID: <your client id>
     SPOTIFY_CLIENT_SECRET: <your client secret>
   ```

3. Deploy the want with the name `my-spotify`:

   ```sh
   mywant wants create -f - <<'YAML'
   wants:
     - metadata:
         name: my-spotify
         type: spotify
       spec:
         params: {}
   YAML
   ```

   The name matters: the OAuth `state` parameter carries it, and that is how the
   callback finds the want to hand the authorization code to. The
   "Connect to Spotify" button rendered on the card is hardwired to
   `my-spotify`; other names work only via `oauth_helper.py --want-name`.

4. Authorize:

   ```sh
   SPOTIFY_CLIENT_ID=xxx SPOTIFY_CLIENT_SECRET=yyy \
     python3 ~/.mywant/custom-types/mywant-spotify-plugin/oauth_helper.py \
     --want-name my-spotify
   ```

   Approve in the browser that opens. The want picks up the code on its next
   tick and exchanges it for a refresh token. This is a one-time step.

   As an alternative to steps 3–4, deploy the want first and click
   **Connect to Spotify** on the card — the same flow, driven from the UI.

## Requirements

- Python 3.10+ (standard library; `certifi` is used if present)
- A Spotify account. **Premium is required for playback control** — the Web API
  rejects play/pause/next/volume on free accounts. Now-playing display works on
  free accounts.
- An active Spotify device. Spotify will not start playback on a device that
  isn't running, so `play` falls back to the first available device and reports
  "No available Spotify device found" if there is none.

## Files

| File | Purpose |
| :--- | :--- |
| `spotify.yaml` | want type: state fields, MRS monitor config, examples |
| `main.py` | polls the Web API, refreshes tokens, executes playback actions |
| `oauth_helper.py` | one-time authorization helper |
| `view/plugin.jsx` | want card UI (artwork, progress bar, transport controls) |

## Notes

- The card responds to width: narrow shows the compact player, wide adds a large
  album-art panel.
- On HTTP 429 the monitor records `rate_limit_until` and backs off until it
  passes, rather than hammering the API.
