import { ConnectionState, type MessageType } from '@/types/server'
import { serverConnection } from '@/hooks/use-server'
import { useRealtimeStore } from './realtime'

// Message types the overlays subscribe to from ServerConnection.
const MESSAGE_TYPES: MessageType[] = [
  'alert:show',
  'alerts:sync',
  'alerts:push',
  'ffbot:stats',
  'ffbot:hire',
  'ffbot:change',
  'ffbot:save',
  'timeline:push',
  'timeline:sync',
  'chat:message',
  'chat:sync',
  'campaign:sync',
  'campaign:update',
  'campaign:milestone',
  'campaign:timer:started',
  'campaign:timer:paused',
  'campaign:timer:tick',
  'limitbreak:executed',
  'limitbreak:sync',
  'limitbreak:update',
  'music:sync',
  'music:update',
  'status:sync',
  'status:update',
  'stream:sync',
  'stream:update',
  'audio:rme:status',
  'audio:rme:update',
  'obs:sync',
  'obs:update',
]

// Wire the realtime transport into the store and open the connection.
//
// Call this once at app bootstrap (main.tsx). Keeping it out of the store
// module means importing the store no longer performs network I/O, so the
// store and its pure logic are testable in isolation.
export function connectRealtime(): void {
  MESSAGE_TYPES.forEach((messageType) => {
    serverConnection.subscribe(messageType, (payload) => {
      useRealtimeStore.getState().updateMessage(messageType, payload)
    })
  })

  // Connection state changes
  serverConnection.subscribe('__connection__' as MessageType, (payload) => {
    const connected = Boolean(payload)
    useRealtimeStore
      .getState()
      .setConnectionStatus(connected, serverConnection.getConnectionState())
  })

  // Ensure connection is established
  if (serverConnection.getConnectionState() === ConnectionState.Disconnected) {
    serverConnection.connect()
  }
}
