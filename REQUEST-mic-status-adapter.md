# Request: a small standalone adapter to revive `RMEMicStatus`

Written by a Claude Code session working in `synthmult` (on Demi), 2026-09-03,
for whoever picks this up in this repo. Not urgent, not hard — the store and
components already do the right thing; this is one new file that feeds them.

## Why this exists

`useRME()`/`useMicStatus()` (`src/hooks/use-rme.ts`), the `rme` slice in
`useRealtimeStore` (`src/store/realtime.ts`), and the `audio:rme:status`/
`audio:rme:update` cases in its `updateMessage` switch are all still wired up
and live. Two components already call `useMicStatus()` right now: the omnibar
(`src/components/omnibar/index.tsx:21`) and the coworking status widget
(`src/components/coworking/status.tsx:34`). All of it has read `isMuted:
false` unconditionally since this repo's own commit `1cc4d70` (2026-03-03)
deleted the backend that fed it — an "RME module" that talked to Bryan's RME
UCX II over TotalMix's own OSC port 9001.

That backend isn't coming back. `synthmix` (`saya:git/synthmix.git`) now
controls the same physical interface over SysEx, and its `mix watch` loop
already detects mic-mute transitions. It publishes them into a new relay
service, `synthmult` (`omnyist/synthmult`, runs on Demi), which now has a
built and verified `audio` channel: `POST /events/audio/<tenant_slug>/` in,
every WebSocket on `ws/audio/<tenant_slug>/` gets it relayed, plus the last
known state on connect. That side is done — this repo is the only piece
still missing.

## What's missing

Nothing here dispatches to `updateMessage('audio:rme:update', ...)` except
`ServerConnection` (`src/hooks/use-server.ts`), and that class is a hardwired
singleton to exactly one WebSocket — `ws://{VITE_WS_HOST}:{VITE_WS_PORT}/ws/overlay/{VITE_TENANT_SLUG}/`,
which is synthfunc's overlay socket on Saya (`.env` here currently points it
at `saya:7178`). synthmult is a separate service on a separate host (Demi)
with a different envelope shape than synthfunc's `EventType`-keyed one —
verified by reading `use-server.ts` and `types/server.ts` directly, not
assumed. Extending `ServerConnection` to juggle two backends would be the
wrong shape for what's a single extra event stream; a second, small,
independent connection is the right size for this.

## What to build

One new file, something like `src/lib/mic-status-adapter.ts`: a minimal
WebSocket client that connects to synthmult's audio channel and forwards
verbatim into the existing store action — it does not need its own
reconnect/cache/subscriber machinery, `ServerConnection`'s complexity exists
for a socket carrying a dozen-plus message types, not one.

```ts
import { useRealtimeStore } from '@/store/realtime'

const HOST = import.meta.env.VITE_SYNTHMULT_WS_HOST || 'demi'
const PORT = import.meta.env.VITE_SYNTHMULT_WS_PORT || '8850'
const SLUG = import.meta.env.VITE_TENANT_SLUG || 'avalonstar'

export function connectMicStatus(): void {
  const url = `ws://${HOST}:${PORT}/ws/audio/${SLUG}/`
  const ws = new WebSocket(url)

  ws.onmessage = (event) => {
    const { event_type, data } = JSON.parse(event.data)
    if (event_type === 'audio:rme:update' || event_type === 'audio:rme:status') {
      useRealtimeStore.getState().updateMessage(event_type, data)
    }
  }

  // Reconnect story still needs designing -- see "What this doesn't solve"
  // below. A flat setTimeout retry is the minimum, not the final answer.
  ws.onclose = () => setTimeout(connectMicStatus, DEFAULT_RECONNECT_DELAY)
}
```

Call `connectMicStatus()` once at bootstrap, alongside `connectRealtime()` in
`main.tsx` — same pattern, second independent connection, not a replacement.

Note synthmult's wire envelope is `{event_type, data, timestamp}`, one level
deeper than `ServerConnection`'s messages — `data` there is exactly the
`RMEMicStatus` shape (`{channel, muted, timestamp}`), so `updateMessage`
receives the same payload shape it already expects from the old backend.
Nothing in the store or either component needs to change.

## What this doesn't solve

- **Reconnect story.** synthmult is co-resident with OBS on Demi, not an
  always-on Saya service — it can restart while this page is open, or not be
  up yet when the page loads. `ServerConnection` already has backoff/retry
  built in; this adapter needs at least a basic version of the same, not the
  bare `onclose` handler sketched above.
- **`VITE_SYNTHMULT_WS_HOST`/`VITE_SYNTHMULT_WS_PORT`** aren't in `.env` yet
  here — need adding once the real deployed host is settled (this session
  only confirmed `demi:8850` reachable from Demi itself, not from wherever
  this frontend is actually served).
- **End-to-end proof.** Nothing has verified an actual `mix mute mic` on
  Demi reaches this frontend's `isMuted` yet — that also needs synthmix's own
  producer pointed at a real `SYNTHMULT_API_KEY`/`SYNTHMULT_URL`, which is
  separate work, tracked in `synthmult`'s own `REQUEST-audio-channel.md`.

## Explicitly out of scope here

Whether `audio:rme:status` (full-state sync) ever gets sent by anything —
synthmix's `mix watch` loop only sends `audio:rme:update` today. The store
and this adapter both already handle either identically, so there's nothing
to build for it now; just don't assume `:status` is exercised by any current
producer.
