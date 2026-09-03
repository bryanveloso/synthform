import type { MessageType } from '@/types/server'
import type { RMEMicStatus } from '@/hooks/use-rme'
import { useRealtimeStore } from '@/store/realtime'

const HOST = import.meta.env.VITE_SYNTHMULT_WS_HOST || 'demi'
const PORT = import.meta.env.VITE_SYNTHMULT_WS_PORT || '8850'
const SLUG = import.meta.env.VITE_TENANT_SLUG || 'avalonstar'

const RECONNECT_DELAY = 1000
const MAX_RECONNECT_DELAY = 30000

let ws: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let attempts = 0

function scheduleReconnect(): void {
  const delay = Math.min(RECONNECT_DELAY * Math.pow(2, attempts), MAX_RECONNECT_DELAY)
  attempts++
  console.log(`[mic-status] reconnecting in ${delay}ms (attempt ${attempts})`)
  reconnectTimer = setTimeout(connectMicStatus, delay)
}

// Second independent WebSocket — connects to synthmult's audio channel on
// Demi, not to synthfunc's overlay socket on Saya.
export function connectMicStatus(): void {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return
  }

  if (reconnectTimer !== null) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${protocol}//${HOST}:${PORT}/ws/audio/${SLUG}/`

  try {
    ws = new WebSocket(url)
  } catch {
    scheduleReconnect()
    return
  }

  ws.onopen = () => {
    attempts = 0
    console.log('[mic-status] connected to synthmult')
  }

  ws.onmessage = (event: MessageEvent) => {
    try {
      const envelope = JSON.parse(event.data) as {
        event_type: string
        data: RMEMicStatus
        timestamp: string
      }
      if (
        envelope.event_type === 'audio:rme:update' ||
        envelope.event_type === 'audio:rme:status'
      ) {
        useRealtimeStore
          .getState()
          .updateMessage(envelope.event_type as MessageType, envelope.data)
      }
    } catch {
      // malformed message — skip
    }
  }

  ws.onerror = () => {
    console.log('[mic-status] connection error')
  }

  ws.onclose = () => {
    ws = null
    console.log('[mic-status] disconnected')
    scheduleReconnect()
  }
}
