// Spotify card plugin — JIT loaded from ~/.mywant/custom-types/mywant-spotify-plugin/view/plugin.jsx
// window.React and window.__mywant are provided by the host app.
const React = window.React;

const SPOTIFY_GREEN = '#1DB954';

function fmtMs(ms) {
  if (!ms || ms <= 0) return '0:00';
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
  return `${m}:${String(sec).padStart(2,'0')}`;
}

async function sendAction(wantId, action) {
  try {
    await fetch(`/api/v1/states/${wantId}/spotify_action`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(action),
    });
  } catch {}
}

function ControlBtn({ onClick, title, children, size = 'sm' }) {
  const [hovered, setHovered] = React.useState(false);
  const pad = size === 'xl' ? '10px' : size === 'lg' ? '6px' : '4px';
  return React.createElement('button', {
    onClick,
    title,
    onMouseEnter: () => setHovered(true),
    onMouseLeave: () => setHovered(false),
    style: {
      background: 'transparent',
      border: 'none',
      cursor: 'pointer',
      padding: pad,
      borderRadius: '50%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: hovered ? '#fff' : 'rgba(255,255,255,0.85)',
      transform: hovered ? 'scale(1.12)' : 'scale(1)',
      transition: 'color 0.15s, transform 0.1s',
    },
  }, children);
}

function SpotifyContentSection({ want }) {
  const id = want.metadata?.id ?? want.id ?? want.metadata?.name ?? '';
  const cur = want.state?.current ?? {};

  const trackName    = cur.track_name    || '';
  const artistName   = cur.artist_name   || '';
  const albumName    = cur.album_name    || '';
  const albumArtUrl  = cur.album_art_url || '';
  const isPlaying    = !!cur.is_playing;
  const progressMs   = Number(cur.progress_ms) || 0;
  const durationMs   = Number(cur.duration_ms) || 0;
  const deviceName   = cur.device_name   || '';
  const volumePct    = Number(cur.volume_percent) || 0;
  const lastError    = cur.last_error    || '';
  const pendingAction = cur.spotify_action || '';
  const oauthUrl     = cur.oauth_url     || '';

  const [localProgress, setLocalProgress] = React.useState(progressMs);
  const intervalRef = React.useRef(null);

  React.useEffect(() => { setLocalProgress(progressMs); }, [progressMs]);
  React.useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (isPlaying) {
      intervalRef.current = setInterval(() => {
        setLocalProgress(p => Math.min(p + 1000, durationMs));
      }, 1000);
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [isPlaying, durationMs]);

  const pct = durationMs > 0 ? Math.min(100, (localProgress / durationMs) * 100) : 0;
  const hasTrack = !!trackName;
  const actionPending = !!pendingAction;

  const handlePlay = () => sendAction(id, isPlaying ? 'pause' : 'play');
  const handleNext = () => sendAction(id, 'next');
  const handlePrev = () => sendAction(id, 'previous');

  const e = React.createElement;

  // ── Icons ────────────────────────────────────────────────────────────────────
  const mkSpinner = (sz) => e('svg', {
    width: sz, height: sz, viewBox: '0 0 24 24', fill: 'none',
    style: { animation: 'spotify-spin 1s linear infinite' },
  }, e('circle', { cx: 12, cy: 12, r: 9, stroke: SPOTIFY_GREEN, strokeWidth: 2.5, strokeDasharray: '40 20' }));

  const mkPlay = (sz) => isPlaying
    ? e('svg', { width: sz, height: sz, viewBox: '0 0 24 24', fill: SPOTIFY_GREEN }, e('path', { d: 'M6 19h4V5H6v14zm8-14v14h4V5h-4z' }))
    : e('svg', { width: sz, height: sz, viewBox: '0 0 24 24', fill: SPOTIFY_GREEN }, e('path', { d: 'M8 5v14l11-7z' }));

  const mkPrev = (sz) => e('svg', { width: sz, height: sz, viewBox: '0 0 24 24', fill: 'currentColor' }, e('path', { d: 'M6 6h2v12H6zm3.5 6 8.5 6V6z' }));
  const mkNext = (sz) => e('svg', { width: sz, height: sz, viewBox: '0 0 24 24', fill: 'currentColor' }, e('path', { d: 'M16 6h2v12h-2zm-1.5 6L6 6v12z' }));

  const speakerIcon = (sz) => e('svg', { width: sz, height: sz, viewBox: '0 0 24 24', fill: 'currentColor' },
    e('path', { d: 'M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z' }));

  const noArtIcon = (sz) => e('svg', { width: sz, height: sz, viewBox: '0 0 24 24', fill: 'none' },
    e('circle', { cx: 12, cy: 12, r: 10, stroke: 'rgba(255,255,255,0.2)', strokeWidth: 2 }),
    e('circle', { cx: 12, cy: 12, r: 3, fill: 'rgba(255,255,255,0.3)' }),
  );

  // ── No-track fallback ─────────────────────────────────────────────────────────
  if (!hasTrack) {
    let msg;
    if (oauthUrl) {
      msg = e('div', { style: { display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'center' } },
        e('div', { style: { color: 'rgba(255,255,255,0.5)', fontSize: 12 } }, 'Spotify に接続が必要です'),
        e('a', {
          href: oauthUrl, target: '_blank', rel: 'noreferrer',
          style: {
            display: 'inline-flex', alignItems: 'center', gap: 6,
            background: SPOTIFY_GREEN, color: '#000', fontWeight: 700, fontSize: 13,
            padding: '6px 16px', borderRadius: 20, textDecoration: 'none',
          },
        }, 'Connect to Spotify'),
      );
    } else if (lastError) {
      msg = e('div', { style: { display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'center' } },
        e('div', { style: { color: '#ff6b6b', fontSize: 12, lineHeight: 1.5, textAlign: 'center', padding: '0 16px' } }, lastError),
        e(ControlBtn, { onClick: () => sendAction(id, 'play'), title: 'Play', size: 'lg' }, actionPending ? mkSpinner(22) : mkPlay(22)),
      );
    } else {
      // Nothing playing (and no error/oauth issue) — still offer a Play button
      // so playback can be started remotely without needing track info first.
      msg = e('div', { style: { display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'center' } },
        e('div', { style: { color: 'rgba(255,255,255,0.35)', fontSize: 13 } }, '再生なし'),
        e(ControlBtn, { onClick: () => sendAction(id, 'play'), title: 'Play', size: 'lg' }, actionPending ? mkSpinner(22) : mkPlay(22)),
      );
    }
    return e('div', {
      style: { borderRadius: 12, background: 'linear-gradient(135deg,#191414,#282828)', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' },
    }, msg);
  }

  // ── Responsive layout via CSS container queries ───────────────────────────────
  // wc-auto is the root element so height:100% resolves directly against the flex parent.
  // wc-main: compact player (always visible)
  // wc-aside: large album art (appears when card is wide, e.g. maximized)
  return e('div', {
    className: 'wc-auto',
    style: {
      position: 'relative', overflow: 'hidden',
      borderRadius: 12, background: 'linear-gradient(135deg, #191414 0%, #282828 100%)',
    },
  },
    // Blurred album art background (absolute, behind grid cells)
    albumArtUrl ? e('div', { style: {
      position: 'absolute', inset: 0, zIndex: 0,
      backgroundImage: `url(${albumArtUrl})`,
      backgroundSize: 'cover', backgroundPosition: 'center',
      opacity: 0.18, filter: 'blur(8px)', transform: 'scale(1.1)',
    }}) : null,

    e('style', null, '@keyframes spotify-spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}'),

      // ── Main: compact player ─────────────────────────────────────────────────
      e('div', { className: 'wc-main', style: { justifyContent: 'center', position: 'relative', zIndex: 1 } },
        e('div', { style: { padding: '10px 12px 8px', display: 'flex', flexDirection: 'column', gap: 6 } },
          // Thumb + info row
          e('div', { style: { display: 'flex', gap: 10, alignItems: 'center' } },
            e('div', { style: { width: 56, height: 56, borderRadius: 6, overflow: 'hidden', flexShrink: 0, background: '#333', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 8px rgba(0,0,0,0.5)' } },
              albumArtUrl
                ? e('img', { src: albumArtUrl, alt: albumName, style: { width: '100%', height: '100%', objectFit: 'cover' } })
                : noArtIcon(24)
            ),
            e('div', { style: { flex: 1, minWidth: 0 } },
              e('div', { style: { color: '#fff', fontSize: 13, fontWeight: 600, lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, trackName),
              e('div', { style: { color: 'rgba(255,255,255,0.6)', fontSize: 11, marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, artistName),
              albumName ? e('div', { style: { color: 'rgba(255,255,255,0.4)', fontSize: 10, marginTop: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, albumName) : null,
            ),
          ),
          // Progress bar
          e('div', { style: { display: 'flex', alignItems: 'center', gap: 6 } },
            e('span', { style: { color: 'rgba(255,255,255,0.5)', fontSize: 9, width: 28, textAlign: 'right' } }, fmtMs(localProgress)),
            e('div', { style: { flex: 1, height: 3, background: 'rgba(255,255,255,0.15)', borderRadius: 2, overflow: 'hidden' } },
              e('div', { style: { width: `${pct}%`, height: '100%', background: SPOTIFY_GREEN, borderRadius: 2, transition: 'width 0.5s linear' } })
            ),
            e('span', { style: { color: 'rgba(255,255,255,0.5)', fontSize: 9, width: 28 } }, fmtMs(durationMs)),
          ),
          // Controls
          e('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4, marginTop: 2 } },
            e(ControlBtn, { onClick: handlePrev, title: 'Previous' }, mkPrev(16)),
            e(ControlBtn, { onClick: handlePlay, title: isPlaying ? 'Pause' : 'Play', size: 'lg' }, actionPending ? mkSpinner(22) : mkPlay(22)),
            e(ControlBtn, { onClick: handleNext, title: 'Next' }, mkNext(16)),
            deviceName ? e('div', {
              style: { marginLeft: 'auto', color: 'rgba(255,255,255,0.35)', fontSize: 9, display: 'flex', alignItems: 'center', gap: 3, maxWidth: 80, overflow: 'hidden' },
              title: `${deviceName} — Volume ${volumePct}%`,
            }, speakerIcon(9), e('span', { style: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, deviceName)) : null,
          ),
        ),
      ),

      // ── Aside: large album art (visible when card is wide) ───────────────────
      e('div', { className: 'wc-aside', style: { alignItems: 'center', justifyContent: 'center', padding: '12px 12px 12px 0', position: 'relative', zIndex: 1 } },
        e('div', { className: 'wc-sp-art-container', style: {
          width: '100%', height: '100%', maxWidth: 280, maxHeight: 280,
          borderRadius: 10, overflow: 'hidden',
          boxShadow: '0 12px 40px rgba(0,0,0,0.6)',
          background: '#333',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }},
          albumArtUrl
            ? e('img', { src: albumArtUrl, alt: albumName, style: { width: '100%', height: '100%', objectFit: 'cover', display: 'block' } })
            : noArtIcon(64)
        ),
      ),
  );
}

window.__mywant.registerPlugin({
  types: ['spotify'],
  ContentSection: SpotifyContentSection,
  hideFinalResult: true,
});
