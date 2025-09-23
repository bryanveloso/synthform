import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'
import {
  ConnectionState,
  type MessageType,
  type PayloadType,
  type AlertData,
  type FFBotStatsMessage,
  type FFBotHireMessage,
  type FFBotChangeMessage,
  type FFBotSaveMessage,
  type ChatMessage,
  type LimitBreakData,
  type LimitBreakExecutedData,
  type StreamStatus,
  type OBSSceneData,
  type OBSStreamData,
} from '@/types/server'
import type { TimelineEvent } from '@/types/events'
import type { MusicData } from '@/types/music'
import type { RMEMicStatus } from '@/hooks/use-rme'
import type {
  Campaign,
  CampaignUpdatePayload,
  MilestoneUnlockedPayload,
  TimerUpdatePayload,
} from '@/types/campaign'
import { serverConnection } from '@/hooks/use-server'

// Alert queue state from use-alerts
interface AlertQueueState {
  currentAlert: AlertData | null
  queue: AlertData[]
  isAnimating: boolean
  isPaused: boolean
  displayDuration: number
}

// FFBot state from use-ffbot
type FFBotMessage = FFBotStatsMessage | FFBotHireMessage | FFBotChangeMessage | FFBotSaveMessage

interface FFBotState {
  events: FFBotMessage[]
  playerActivity: Map<string, Array<{
    type: string
    timestamp: string
    data: any
  }>>
  latestEvent: FFBotMessage | null
  maxEvents: number
}

// Timeline state
interface TimelineState {
  events: TimelineEvent[]
  latestEvent: TimelineEvent | null
}

// Chat state
interface ChatState {
  messages: ChatMessage[]
  maxMessages: number
}

// Complete store interface
interface RealtimeStore {
  // Connection state
  isConnected: boolean
  connectionState: ConnectionState

  // Alert queue state
  alerts: AlertQueueState

  // FFBot state
  ffbot: FFBotState

  // Timeline state
  timeline: TimelineState

  // Chat state
  chat: ChatState

  // Campaign state
  campaign: Campaign | null
  campaignUpdate: CampaignUpdatePayload | null
  milestoneUnlocked: MilestoneUnlockedPayload | null
  timerUpdate: TimerUpdatePayload | null

  // Limit break state
  limitbreak: LimitBreakData | null
  limitbreakExecuted: LimitBreakExecutedData | null

  // Music state
  music: MusicData | null

  // Stream status
  status: StreamStatus | null

  // RME audio state
  rme: RMEMicStatus | null

  // OBS state
  obs: {
    scene: OBSSceneData | null
    stream: OBSStreamData | null
  }

  // Actions
  updateMessage: <T extends MessageType>(
    messageType: T,
    payload: PayloadType<T>
  ) => void
  setConnectionStatus: (connected: boolean, state: ConnectionState) => void

  // Alert queue actions (from use-alerts logic)
  addAlert: (alert: AlertData) => void
  removeCurrentAlert: () => void
  clearAlertQueue: () => void
  setAlertAnimating: (isAnimating: boolean) => void
  setPausedState: (isPaused: boolean) => void

  // FFBot actions (from use-ffbot logic)
  addFFBotEvent: (event: FFBotMessage) => void

  // Timeline actions
  addTimelineEvent: (event: TimelineEvent) => void
  syncTimeline: (events: TimelineEvent[]) => void

  // Chat actions
  addChatMessage: (message: ChatMessage) => void
}

// Create the store
export const useRealtimeStore = create<RealtimeStore>()(
  subscribeWithSelector((set, get) => ({
    // Initial state
    isConnected: serverConnection.isConnected(),
    connectionState: serverConnection.getConnectionState(),

    // Alert queue initial state
    alerts: {
      currentAlert: null,
      queue: [],
      isAnimating: false,
      isPaused: false,
      displayDuration: 5000,
    },

    // FFBot initial state
    ffbot: {
      events: [],
      playerActivity: new Map(),
      latestEvent: null,
      maxEvents: 100,
    },

    // Timeline initial state
    timeline: {
      events: [],
      latestEvent: null,
    },

    // Chat initial state
    chat: {
      messages: [],
      maxMessages: 50,
    },

    // Campaign initial state
    campaign: null,
    campaignUpdate: null,
    milestoneUnlocked: null,
    timerUpdate: null,

    // Other states
    limitbreak: null,
    limitbreakExecuted: null,
    music: null,
    status: null,
    rme: null,
    obs: {
      scene: null,
      stream: null,
    },

    // Generic update action
    updateMessage: (messageType, payload) => {
      const state = get()

      switch (messageType) {
        // Alert messages
        case 'alert:show':
          state.addAlert(payload as AlertData)
          break
        case 'alerts:sync':
          set({ alerts: { ...state.alerts, queue: payload as AlertData[] } })
          break
        case 'alerts:push':
          state.addAlert(payload as AlertData)
          break

        // FFBot messages
        case 'ffbot:stats':
        case 'ffbot:hire':
        case 'ffbot:change':
        case 'ffbot:save':
          state.addFFBotEvent(payload as any)
          break

        // Timeline messages
        case 'timeline:push':
          state.addTimelineEvent(payload as TimelineEvent)
          break
        case 'timeline:sync':
          state.syncTimeline(payload as TimelineEvent[])
          break

        // Chat messages
        case 'chat:message':
          state.addChatMessage(payload as ChatMessage)
          break

        // Campaign messages
        case 'campaign:sync':
          set({ campaign: payload as Campaign })
          break
        case 'campaign:update':
          set({ campaignUpdate: payload as CampaignUpdatePayload })
          break
        case 'campaign:milestone':
          set({ milestoneUnlocked: payload as MilestoneUnlockedPayload })
          break
        case 'campaign:timer:started':
        case 'campaign:timer:paused':
        case 'campaign:timer:tick':
          set({ timerUpdate: payload as TimerUpdatePayload })
          break

        // Limit break messages
        case 'limitbreak:sync':
        case 'limitbreak:update':
          set({ limitbreak: payload as LimitBreakData })
          break
        case 'limitbreak:executed':
          set({ limitbreakExecuted: payload as LimitBreakExecutedData })
          break

        // Music messages
        case 'music:sync':
        case 'music:update':
          set({ music: payload as MusicData })
          break

        // Status messages
        case 'status:sync':
        case 'status:update':
          set({ status: payload as StreamStatus })
          break

        // RME messages
        case 'audio:rme:status':
        case 'audio:rme:update':
          set({ rme: payload as RMEMicStatus })
          break

        // OBS messages
        case 'obs:sync':
          set({
            obs: {
              scene: (payload as any).scene || state.obs.scene,
              stream: (payload as any).stream || state.obs.stream,
            },
          })
          break
        case 'obs:update':
          set({
            obs: {
              ...state.obs,
              stream: payload as OBSStreamData,
            },
          })
          break
      }
    },

    setConnectionStatus: (connected, connectionState) => {
      set({ isConnected: connected, connectionState })
    },

    // Alert queue actions (copied from use-alerts)
    addAlert: (alert) => {
      set((state) => ({
        alerts: {
          ...state.alerts,
          queue: [...state.alerts.queue, alert],
        },
      }))
    },

    removeCurrentAlert: () => {
      set((state) => ({
        alerts: {
          ...state.alerts,
          currentAlert: null,
        },
      }))
    },

    clearAlertQueue: () => {
      set((state) => ({
        alerts: {
          ...state.alerts,
          queue: [],
          currentAlert: null,
        },
      }))
    },

    setAlertAnimating: (isAnimating) => {
      set((state) => ({
        alerts: {
          ...state.alerts,
          isAnimating,
        },
      }))
    },

    setPausedState: (isPaused) => {
      set((state) => ({
        alerts: {
          ...state.alerts,
          isPaused,
        },
      }))
    },

    // FFBot actions (copied from use-ffbot)
    addFFBotEvent: (event) => {
      set((state) => {
        const events = [...state.ffbot.events, event]

        // Trim events if exceeding max
        if (events.length > state.ffbot.maxEvents) {
          events.splice(0, events.length - state.ffbot.maxEvents)
        }

        // Update player activity tracking
        const playerActivity = new Map(state.ffbot.playerActivity)
        if ('player' in event && event.player) {
          const activities = playerActivity.get(event.player) || []

          // Determine event type from message structure
          let eventType = 'unknown'
          if ('character' in event && 'cost' in event) {
            eventType = 'hire'
          } else if ('from' in event && 'to' in event) {
            eventType = 'change'
          } else if ('data' in event) {
            eventType = 'stats'
          } else if ('player_count' in event) {
            eventType = 'save'
          }

          activities.push({
            type: eventType,
            timestamp: event.timestamp,
            data: event,
          })

          // Keep only last 10 activities per player
          if (activities.length > 10) {
            activities.splice(0, activities.length - 10)
          }

          playerActivity.set(event.player, activities)
        }

        return {
          ffbot: {
            ...state.ffbot,
            events,
            playerActivity,
            latestEvent: event,
          },
        }
      })
    },

    // Timeline actions
    addTimelineEvent: (event) => {
      set((state) => ({
        timeline: {
          events: [...state.timeline.events, event],
          latestEvent: event,
        },
      }))
    },

    syncTimeline: (events) => {
      set({
        timeline: {
          events,
          latestEvent: events[events.length - 1] || null,
        },
      })
    },

    // Chat actions
    addChatMessage: (message) => {
      set((state) => {
        const messages = [...state.chat.messages, message]

        // Trim messages if exceeding max
        if (messages.length > state.chat.maxMessages) {
          messages.splice(0, messages.length - state.chat.maxMessages)
        }

        return {
          chat: {
            ...state.chat,
            messages,
          },
        }
      })
    },
  }))
)

// Subscribe to all message types from ServerConnection
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
  'audio:rme:status',
  'audio:rme:update',
  'obs:sync',
  'obs:update',
]

// Set up subscriptions when the module loads
MESSAGE_TYPES.forEach((messageType) => {
  serverConnection.subscribe(messageType, (payload) => {
    useRealtimeStore.getState().updateMessage(messageType, payload)
  })
})

// Subscribe to connection state changes
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