import type { TimelineEvent } from './events'
import type { MusicData } from './music'

// Connection state enum
export enum ConnectionState {
  Disconnected = 'disconnected',
  Connecting = 'connecting',
  Connected = 'connected',
}

// Stream status types
export interface StreamStatus {
  status: 'online' | 'away' | 'busy' | 'brb' | 'focus'
  message: string
  updated_at: string | null
}

// Limit break types
export interface LimitBreakData {
  count: number
  bar1: number
  bar2: number
  bar3: number
  isMaxed: boolean
}

export interface LimitBreakExecutedData {
  executed_at: string
  executed_by: string
  count: number
}

// Chat message types
export interface ChatEmote {
  id: string
  emote_set_id: string
}

export interface ChatFragment {
  type: string
  text: string
  emote?: ChatEmote
}

export interface ChatMessagePayload {
  id: string
  text: string
  user_name: string
  user_display_name: string
  fragments: ChatFragment[]
}

// Chat message as received from the server (with wrapper)
export interface ChatMessageData {
  data: ChatMessagePayload
}

// OBS types
export interface OBSSceneData {
  current_scene: string
  scenes: string[]
}

export interface OBSStreamData {
  streaming: boolean
  recording: boolean
  stream_time?: number
  record_time?: number
}

// Alert types
export interface AlertData {
  id: string
  type: string
  message: string
  user_name?: string
  amount?: number
  timestamp: string
}

// Ticker types (for bottom bar messages)
export interface TickerData {
  messages: string[]
  current_index: number
  rotation_interval: number
}

// Base message structure from WebSocket
export interface ServerMessage<T = unknown> {
  type: string
  payload: T
  timestamp: string
  sequence: number
}

// Map of message types to their payload types
export interface MessagePayloadMap {
  'base:sync': Record<string, unknown>
  'base:update': Record<string, unknown>
  'timeline:push': TimelineEvent
  'timeline:sync': TimelineEvent[]
  'obs:update': OBSStreamData
  'obs:sync': OBSSceneData & OBSStreamData
  'ticker:sync': TickerData
  'alert:show': AlertData
  'alerts:sync': AlertData[]
  'alerts:push': AlertData
  'limitbreak:executed': LimitBreakExecutedData
  'limitbreak:sync': LimitBreakData
  'limitbreak:update': LimitBreakData
  'music:sync': MusicData
  'music:update': MusicData
  'status:sync': StreamStatus
  'status:update': StreamStatus
  'chat:message': ChatMessageData
}

// Extract valid message types
export type MessageType = keyof MessagePayloadMap

// Get payload type for a specific message type
export type PayloadType<T extends MessageType> = MessagePayloadMap[T]

// Typed server message
export type TypedServerMessage<T extends MessageType = MessageType> = {
  type: T
  payload: PayloadType<T>
  timestamp: string
  sequence: number
}

// Connection options for the hook
export interface UseServerOptions {
  // Cache configuration
  useCache?: boolean
  cacheTTL?: number // in milliseconds

  // Error handling
  onError?: (error: Error) => void
  onConnectionChange?: (connected: boolean) => void

  // Retry configuration
  maxReconnectAttempts?: number
  reconnectDelay?: number
}

// Typed data structure for useServer hook
export type ServerData<T extends readonly MessageType[]> = {
  [K in T[number]]: PayloadType<K> | undefined
}

// Cache entry with TTL
export interface CacheEntry<T = unknown> {
  data: T
  timestamp: number
  ttl: number
}