import type { TimelineEvent } from './events'
import type { MusicData } from './music'
import type {
  OBSStatusMessage,
  OBSSceneChangedMessage,
  OBSScenesListMessage,
  OBSSceneItemsMessage,
  OBSStreamStatusMessage,
  RefreshBrowserSourceCommand,
  SetSceneCommand,
} from './obs'
import type { RMEMicStatus } from '@/hooks/use-rme'
import type {
  Campaign,
  CampaignUpdatePayload,
  MilestoneUnlockedPayload,
  TimerUpdatePayload,
} from './campaign'

// Connection state
export const ConnectionState = {
  Disconnected: 'disconnected',
  Connecting: 'connecting',
  Connected: 'connected',
} as const

export type ConnectionState = typeof ConnectionState[keyof typeof ConnectionState]

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

export interface EmoteFragment {
  type: string
  text: string
  emote?: ChatEmote
}

export interface ChatMessage {
  id: string
  text: string
  user_name: string
  user_display_name: string
  fragments: EmoteFragment[]
}

// FFBot types
export interface FFBotMember {
  id: string
  username: string
  display_name: string
}

export interface FFBotStatsData {
  lv: number
  atk: number
  mag: number
  spi: number
  hp: number
  collection: number
  ascension: number
  wins: number
  preference?: string
  esper?: string
  artifact?: string
  job?: string
  job_level?: number
}

export interface FFBotStatsMessage {
  player: string
  member?: FFBotMember
  data: FFBotStatsData
  timestamp: string
}

export interface FFBotHireMessage {
  player: string
  member?: FFBotMember
  character: string
  cost: number
  timestamp: string
}

export interface FFBotChangeMessage {
  player: string
  member?: FFBotMember
  from: string
  to: string
  timestamp: string
}

export interface FFBotSaveMessage {
  player_count: number
  metadata?: Record<string, any>
  timestamp: string
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
  'obs:status': OBSStatusMessage
  'obs:scene:changed': OBSSceneChangedMessage
  'obs:stream:started': Record<string, never>
  'obs:stream:stopped': Record<string, never>
  'obs:record:started': Record<string, never>
  'obs:record:stopped': Record<string, never>
  'obs:virtualcam:started': Record<string, never>
  'obs:virtualcam:stopped': Record<string, never>
  'obs:scenes:list': OBSScenesListMessage
  'obs:scene:items': OBSSceneItemsMessage
  'obs:stream:status': OBSStreamStatusMessage
  'obs:browser:refresh': RefreshBrowserSourceCommand
  'obs:scene:set': SetSceneCommand
  'obs:stream:start': Record<string, never>
  'obs:stream:stop': Record<string, never>
  'obs:record:start': Record<string, never>
  'obs:record:stop': Record<string, never>
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
  'chat:message': ChatMessage
  'audio:rme:status': RMEMicStatus
  'audio:rme:update': RMEMicStatus
  // FFBot game events
  'ffbot:stats': FFBotStatsMessage
  'ffbot:hire': FFBotHireMessage
  'ffbot:change': FFBotChangeMessage
  'ffbot:save': FFBotSaveMessage
  // Campaign events
  'campaign:sync': Campaign
  'campaign:update': CampaignUpdatePayload
  'campaign:milestone': MilestoneUnlockedPayload
  'campaign:timer:started': TimerUpdatePayload
  'campaign:timer:paused': TimerUpdatePayload
  'campaign:timer:tick': TimerUpdatePayload
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