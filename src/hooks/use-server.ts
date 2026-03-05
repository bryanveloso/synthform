import { ConnectionState } from '@/types/server'
import type {
  MessageType,
  PayloadType,
  ServerMessage,
  CacheEntry,
} from '@/types/server'

// Cache configuration
const DEFAULT_CACHE_TTL = 5 * 60 * 1000 // 5 minutes
const MAX_CACHE_SIZE = 100
const CACHE_CLEANUP_INTERVAL = 60 * 1000 // 1 minute

// Connection configuration
const DEFAULT_RECONNECT_DELAY = 1000
const DEFAULT_MAX_RECONNECT_ATTEMPTS = 10
const MAX_RECONNECT_DELAY = 30000

// Special key for connection state subscribers
type SubscriberKey = MessageType | '__connection__'

class ServerConnection {
  private ws: WebSocket | null = null
  private subscribers = new Map<SubscriberKey, Set<(data: unknown) => void>>()
  private cache = new Map<MessageType, CacheEntry>()
  private connectionState: ConnectionState = ConnectionState.Disconnected
  private reconnectAttempts = 0
  private maxReconnectAttempts = DEFAULT_MAX_RECONNECT_ATTEMPTS
  private reconnectDelay = DEFAULT_RECONNECT_DELAY
  private cacheCleanupTimer: NodeJS.Timeout | null = null
  private reconnectTimer: NodeJS.Timeout | null = null

  constructor() {
    // Start cache cleanup timer
    this.startCacheCleanup()
  }

  private getWebSocketUrl(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const isDev =
      import.meta.env.DEV ||
      window.location.hostname === 'localhost' ||
      window.location.hostname === 'zelan'
    const host = import.meta.env.VITE_WS_HOST || (isDev ? 'synthfunc' : 'saya')
    const port = import.meta.env.VITE_WS_PORT || '7178'
    const slug = import.meta.env.VITE_TENANT_SLUG || 'avalonstar'
    return `${protocol}//${host}:${port}/ws/overlay/${slug}/`
  }

  private startCacheCleanup() {
    this.cacheCleanupTimer = setInterval(() => {
      const now = Date.now()
      const entriesToDelete: MessageType[] = []

      this.cache.forEach((entry, key) => {
        if (now - entry.timestamp > entry.ttl) {
          entriesToDelete.push(key)
        }
      })

      entriesToDelete.forEach((key) => this.cache.delete(key))

      // Also limit cache size
      if (this.cache.size > MAX_CACHE_SIZE) {
        const sortedEntries = Array.from(this.cache.entries()).sort(
          (a, b) => a[1].timestamp - b[1].timestamp,
        )
        const toRemove = sortedEntries.slice(0, this.cache.size - MAX_CACHE_SIZE)
        toRemove.forEach(([key]) => this.cache.delete(key))
      }
    }, CACHE_CLEANUP_INTERVAL)
  }

  connect() {
    if (this.connectionState !== ConnectionState.Disconnected) {
      return
    }

    this.connectionState = ConnectionState.Connecting

    try {
      this.ws = new WebSocket(this.getWebSocketUrl())

      this.ws.onopen = () => {
        console.log('🔌 WebSocket connected to server')
        this.connectionState = ConnectionState.Connected
        this.reconnectAttempts = 0
        this.notifyConnectionChange(true)
      }

      this.ws.onmessage = (event) => {
        this.handleMessage(event)
      }

      this.ws.onclose = () => {
        console.log('🔌 WebSocket disconnected from server')
        this.connectionState = ConnectionState.Disconnected
        this.ws = null
        this.notifyConnectionChange(false)
        this.scheduleReconnect()
      }

      this.ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error)
        this.connectionState = ConnectionState.Disconnected
      }
    } catch (error) {
      console.error('❌ Failed to create WebSocket connection:', error)
      this.connectionState = ConnectionState.Disconnected
      this.scheduleReconnect()
    }
  }

  private handleMessage(event: MessageEvent) {
    try {
      const message = JSON.parse(event.data) as ServerMessage
      const { type, payload } = message

      // Validate message type
      if (!this.isValidMessageType(type)) {
        console.warn(`Unknown message type: ${type}`)
        return
      }

      const messageType = type as MessageType

      // Update cache
      this.cache.set(messageType, {
        data: payload,
        timestamp: Date.now(),
        ttl: DEFAULT_CACHE_TTL,
      })

      // Notify subscribers
      const subscribers = this.subscribers.get(messageType)
      if (subscribers) {
        subscribers.forEach((callback) => {
          try {
            callback(payload)
          } catch (error) {
            console.error(`Error in subscriber callback for ${messageType}:`, error)
          }
        })
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error)
    }
  }

  private isValidMessageType(type: string): type is MessageType {
    const validTypes: MessageType[] = [
      'base:sync',
      'base:update',
      'timeline:push',
      'timeline:sync',
      'obs:update',
      'obs:sync',
      'ticker:sync',
      'alert:show',
      'alerts:sync',
      'alerts:push',
      'limitbreak:executed',
      'limitbreak:sync',
      'limitbreak:update',
      'music:sync',
      'music:update',
      'status:sync',
      'status:update',
      'stream:sync',
      'stream:update',
      'chat:message',
      'chat:sync',
      'audio:rme:status',
      'audio:rme:update',
      'ffbot:stats',
      'ffbot:hire',
      'ffbot:change',
      'ffbot:save',
      'ironmon:init',
      'ironmon:seed',
      'ironmon:checkpoint',
      'ironmon:location',
      'ironmon:battle_started',
      'ironmon:battle_ended',
      'ironmon:team_update',
      'ironmon:item_usage',
      'ironmon:healing_summary',
      'ironmon:trainer_defeated',
      'ironmon:encounter',
      'ironmon:battle_damage',
      'ironmon:battle_action',
      'ironmon:move_history',
      'ironmon:move_effectiveness',
      'ironmon:reset',
      'ironmon:error',
      'campaign:sync',
      'campaign:update',
      'campaign:milestone',
      'campaign:timer:started',
      'campaign:timer:paused',
      'campaign:timer:tick',
    ]
    return validTypes.includes(type as MessageType)
  }

  private scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('❌ Max reconnection attempts reached')
      return
    }

    // Only reconnect if we have active subscribers
    if (this.subscribers.size === 0) {
      return
    }

    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts),
      MAX_RECONNECT_DELAY,
    )
    this.reconnectAttempts++

    console.log(`🔄 Scheduling reconnect attempt ${this.reconnectAttempts} in ${delay}ms`)

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
    }

    this.reconnectTimer = setTimeout(() => {
      if (this.connectionState === ConnectionState.Disconnected && this.subscribers.size > 0) {
        this.connect()
      }
    }, delay)
  }

  subscribe<T extends MessageType>(
    messageType: T,
    callback: (data: PayloadType<T>) => void,
  ): PayloadType<T> | undefined {
    // Initialize subscriber set if it doesn't exist
    if (!this.subscribers.has(messageType)) {
      this.subscribers.set(messageType, new Set())
    }

    // Add callback to subscribers
    this.subscribers.get(messageType)!.add(callback as (data: unknown) => void)

    // Auto-connect if not already connected/connecting
    if (this.connectionState === ConnectionState.Disconnected) {
      this.connect()
    }

    // Return cached data if available
    const cached = this.cache.get(messageType)
    if (cached) {
      return cached.data as PayloadType<T>
    }

    return undefined
  }

  unsubscribe<T extends MessageType>(messageType: T, callback: (data: PayloadType<T>) => void) {
    const subscribers = this.subscribers.get(messageType)
    if (subscribers) {
      subscribers.delete(callback as (data: unknown) => void)

      // Clean up empty subscriber sets
      if (subscribers.size === 0) {
        this.subscribers.delete(messageType)
      }
    }
  }

  isConnected(): boolean {
    return this.connectionState === ConnectionState.Connected
  }

  getConnectionState(): ConnectionState {
    return this.connectionState
  }

  private notifyConnectionChange(connected: boolean) {
    // Notify connection state subscribers using a special key
    const connectionSubscribers = this.subscribers.get('__connection__')
    if (connectionSubscribers) {
      connectionSubscribers.forEach((callback) => {
        try {
          callback(connected)
        } catch (error) {
          console.error('Error in connection subscriber callback:', error)
        }
      })
    }
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }

    if (this.ws) {
      this.ws.close()
      this.ws = null
    }

    this.connectionState = ConnectionState.Disconnected
  }

  clearCache() {
    this.cache.clear()
  }

  send<T extends MessageType>(messageType: T, payload: PayloadType<T>) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message = {
        type: messageType,
        payload,
        timestamp: new Date().toISOString(),
      }
      this.ws.send(JSON.stringify(message))
      return true
    }
    console.warn(`Cannot send message ${messageType}: WebSocket not connected`)
    return false
  }

  destroy() {
    this.disconnect()
    this.subscribers.clear()
    this.cache.clear()
    if (this.cacheCleanupTimer) {
      clearInterval(this.cacheCleanupTimer)
      this.cacheCleanupTimer = null
    }
  }
}

// Singleton instance
const serverConnection = new ServerConnection()

export { serverConnection }
