/* eslint-disable @typescript-eslint/no-explicit-any */
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

// Raw event interface for transformation
interface RawEvent {
  event_id?: string
  id?: string
  event_type?: string
  type?: string
  source?: string
  timestamp?: string
  username?: string
  payload?: Record<string, any>
  data?: {
    timestamp: string
    payload: Record<string, any>
    user_name?: string
  }
}

// Transform raw events to TimelineEvent format
function transformTimelineEvent(rawEvent: RawEvent): TimelineEvent {
  // If it already has the correct structure (from database), return as-is
  if (rawEvent.type && rawEvent.type.includes('.') && rawEvent.data) {
    return rawEvent as TimelineEvent
  }

  // Transform raw event from Redis
  const source = rawEvent.source || 'twitch'
  let eventType = rawEvent.event_type || rawEvent.type || ''

  // Handle consolidated chat.notification events from Twitch
  // These come through with a notice_type that tells us the real event type
  if (eventType === 'channel.chat.notification' && rawEvent.payload?.notice_type) {
    const noticeTypeMap: Record<string, string> = {
      sub: 'channel.subscribe',
      resub: 'channel.subscription.message',
      sub_gift: 'channel.subscription.gift',
      community_sub_gift: 'channel.subscription.gift',
      gift_paid_upgrade: 'channel.subscription.gift',
      prime_paid_upgrade: 'channel.subscribe',
      raid: 'channel.raid',
      unraid: 'channel.raid',
      pay_it_forward: 'channel.subscription.gift',
      announcement: 'channel.announcement',
      bits_badge_tier: 'channel.cheer',
      charity_donation: 'channel.charity_donation',
    }
    eventType = noticeTypeMap[rawEvent.payload.notice_type] || eventType
  }

  return {
    id: rawEvent.event_id || rawEvent.id || `${Date.now()}`,
    type: `${source}.${eventType}`,
    data: {
      timestamp: rawEvent.timestamp || new Date().toISOString(),
      payload: rawEvent.payload || {},
      user_name: rawEvent.username || rawEvent.payload?.user_name || 'Unknown',
    },
  } as TimelineEvent
}

// Constants for gift aggregation
const COMMUNITY_GIFT_DEBOUNCE_MS = 750
const COMMUNITY_GIFT_GC_MS = 30000

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
  playerActivity: Map<
    string,
    Array<{
      type: string
      timestamp: string
      data: any
    }>
  >
  latestEvent: FFBotMessage | null
  maxEvents: number
}

// Timeline state
interface TimelineState {
  events: TimelineEvent[]
  latestEvent: TimelineEvent | null
  maxEvents: number
  lastPushTime: number
  pendingEvents: Map<string, TimelineEvent>
}

// Chat state
interface ChatState {
  messages: ChatMessage[]
  maxMessages: number
}

// Community gift aggregation state
interface PendingCommunityGift {
  gifterEvent: AlertData | null
  individualGifts: AlertData[]
  count: number
  timeoutId: NodeJS.Timeout | null
  gcTimeoutId: NodeJS.Timeout | null
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

  // Community gift aggregation
  pendingCommunityGifts: Map<string, PendingCommunityGift>

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
  updateMessage: <T extends MessageType>(messageType: T, payload: PayloadType<T>) => void
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
  clearTimeline: () => void
  setTimelineMaxEvents: (max: number) => void
  holdTimelineEvent: (event: TimelineEvent) => void
  releaseTimelineEvent: (eventId: string) => void
  hasAlertWithId: (eventId: string) => boolean

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
      maxEvents: 20,
      lastPushTime: 0,
      pendingEvents: new Map(),
    },

    // Chat initial state
    chat: {
      messages: [],
      maxMessages: 50,
    },

    // Community gift aggregation initial state
    pendingCommunityGifts: new Map(),

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
          state.addFFBotEvent(payload as FFBotMessage)
          break

        // Timeline messages
        case 'timeline:push': {
          const timelineEvent = payload as TimelineEvent
          // Server sends alerts:push before timeline:push to ensure alert is in queue
          // If matching alert exists, hold timeline event until alert completes
          if (state.hasAlertWithId(timelineEvent.id)) {
            // Hold the timeline event until alert completes
            state.holdTimelineEvent(timelineEvent)
          } else {
            // No matching alert, add directly to timeline
            state.addTimelineEvent(timelineEvent)
          }
          break
        }
        case 'timeline:sync':
          state.syncTimeline(payload as TimelineEvent[])
          break

        // Chat messages
        case 'chat:message':
          state.addChatMessage(payload as ChatMessage)
          break
        case 'chat:sync':
          // Replace all messages with synced history
          set((state) => ({
            chat: {
              ...state.chat,
              messages: payload as ChatMessage[]
            }
          }))
          break

        // Campaign messages
        case 'campaign:sync':
          set({ campaign: payload as Campaign })
          break
        case 'campaign:update': {
          // Store the update AND merge into main campaign state
          const update = payload as CampaignUpdatePayload
          set((state) => ({
            campaignUpdate: update,
            // Merge the update into the campaign's metric
            campaign: state.campaign
              ? {
                  ...state.campaign,
                  metric: {
                    ...state.campaign.metric,
                    total_subs: update.total_subs ?? state.campaign.metric.total_subs,
                    total_resubs: update.total_resubs ?? state.campaign.metric.total_resubs,
                    total_bits: update.total_bits ?? state.campaign.metric.total_bits,
                    timer_seconds_remaining:
                      update.timer_seconds_remaining ??
                      state.campaign.metric.timer_seconds_remaining,
                    extra_data: update.extra_data ?? state.campaign.metric.extra_data,
                  },
                }
              : null,
          }))
          break
        }
        case 'campaign:milestone': {
          // Store the milestone AND update the campaign's milestones
          const milestone = payload as MilestoneUnlockedPayload
          set((state) => ({
            milestoneUnlocked: milestone,
            // Update the milestone in the campaign's milestones array
            campaign: state.campaign
              ? {
                  ...state.campaign,
                  milestones: state.campaign.milestones.map((m) =>
                    m.id === milestone.id
                      ? { ...m, is_unlocked: true, unlocked_at: new Date().toISOString() }
                      : m,
                  ),
                }
              : null,
          }))
          break
        }
        case 'campaign:timer:started':
        case 'campaign:timer:paused':
        case 'campaign:timer:tick': {
          // Store the timer update AND merge into campaign metric
          const timerPayload = payload as TimerUpdatePayload
          set((state) => ({
            timerUpdate: timerPayload,
            // Update timer fields in the campaign's metric
            campaign: state.campaign
              ? {
                  ...state.campaign,
                  metric: {
                    ...state.campaign.metric,
                    timer_seconds_remaining:
                      timerPayload.timer_seconds_remaining ??
                      state.campaign.metric.timer_seconds_remaining,
                    timer_started_at: timerPayload.timer_started
                      ? new Date().toISOString()
                      : state.campaign.metric.timer_started_at,
                    timer_paused_at: timerPayload.timer_paused
                      ? new Date().toISOString()
                      : timerPayload.timer_started === false
                        ? null
                        : state.campaign.metric.timer_paused_at,
                  },
                }
              : null,
          }))
          break
        }

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
          {
            const obsPayload = payload as PayloadType<'obs:sync'>
            set({
              obs: {
                scene: obsPayload.scene || state.obs.scene,
                stream: obsPayload.stream || state.obs.stream,
              },
            })
          }
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
      const { community_gift_id, type } = alert

      // Skip bundling for community_sub_gift - total already included, recipients suppressed
      if (type === 'community_sub_gift') {
        set((state) => ({
          alerts: {
            ...state.alerts,
            queue: [...state.alerts.queue, alert],
          },
        }))
        return
      }

      // Legacy bundling for individual gifts with community_gift_id
      if (community_gift_id) {
        set((state) => {
          const pendingGifts = new Map(state.pendingCommunityGifts)
          const bundle = pendingGifts.get(community_gift_id) || {
            gifterEvent: null,
            individualGifts: [],
            count: 0,
            timeoutId: null,
            gcTimeoutId: null,
          }

          // Clear existing timeouts to prevent memory leaks
          if (bundle.timeoutId) {
            clearTimeout(bundle.timeoutId)
          }
          if (bundle.gcTimeoutId) {
            clearTimeout(bundle.gcTimeoutId)
          }

          // Clear existing timeout
          if (bundle.timeoutId) {
            clearTimeout(bundle.timeoutId)
          }

          // Store the appropriate event
          if (type === 'community_sub_gift') {
            bundle.gifterEvent = alert
          } else if (type === 'sub_gift') {
            bundle.individualGifts.push(alert)
            bundle.count += alert.amount || 1
          }

          // Set timeout to process the bundle
          bundle.timeoutId = setTimeout(() => {
            set((currentState) => {
              const currentPendingGifts = new Map(currentState.pendingCommunityGifts)
              const completedBundle = currentPendingGifts.get(community_gift_id)

              if (completedBundle) {
                const gifter = completedBundle.gifterEvent?.user_name || 'A kind stranger'
                const totalGifts = completedBundle.individualGifts.length || completedBundle.count

                // Create consolidated alert
                const consolidatedAlert: AlertData = {
                  id: `community-gift-${community_gift_id}`,
                  type: 'community_gift_bundle',
                  message: `${gifter} gifted ${totalGifts} sub${totalGifts !== 1 ? 's' : ''}!`,
                  user_name: gifter,
                  amount: totalGifts,
                  timestamp: completedBundle.gifterEvent?.timestamp || new Date().toISOString(),
                  community_gift_id: community_gift_id,
                  tier:
                    completedBundle.gifterEvent?.tier || completedBundle.individualGifts[0]?.tier,
                }

                // Add to alert queue
                currentPendingGifts.delete(community_gift_id)

                // Also add to timeline as consolidated event
                const timelineEvent: TimelineEvent = {
                  id: consolidatedAlert.id,
                  type: 'twitch.channel.subscription.gift.bundle',
                  data: {
                    timestamp: consolidatedAlert.timestamp,
                    payload: {
                      gifter: gifter,
                      total: totalGifts,
                      tier: consolidatedAlert.tier!,
                    },
                    user_name: gifter,
                  },
                }

                return {
                  alerts: {
                    ...currentState.alerts,
                    queue: [...currentState.alerts.queue, consolidatedAlert],
                  },
                  pendingCommunityGifts: currentPendingGifts,
                  timeline: {
                    ...currentState.timeline,
                    events: [timelineEvent, ...currentState.timeline.events].slice(
                      0,
                      currentState.timeline.maxEvents,
                    ),
                    latestEvent: timelineEvent,
                    lastPushTime: Date.now(),
                  },
                }
              }
              return currentState
            })
          }, COMMUNITY_GIFT_DEBOUNCE_MS)

          // Set garbage collection timeout to clean up orphaned bundles
          bundle.gcTimeoutId = setTimeout(() => {
            set((currentState) => {
              const currentPendingGifts = new Map(currentState.pendingCommunityGifts)
              if (currentPendingGifts.has(community_gift_id)) {
                console.warn(
                  `Garbage collecting incomplete community gift bundle: ${community_gift_id}`,
                )
                currentPendingGifts.delete(community_gift_id)
                return { pendingCommunityGifts: currentPendingGifts }
              }
              return currentState
            })
          }, COMMUNITY_GIFT_GC_MS)

          pendingGifts.set(community_gift_id, bundle)

          return {
            pendingCommunityGifts: pendingGifts,
          }
        })
      } else {
        // Non-community gift, add directly
        set((state) => ({
          alerts: {
            ...state.alerts,
            queue: [...state.alerts.queue, alert],
          },
        }))
      }
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
      set((state) => {
        // Transform the event if needed
        const transformedEvent = transformTimelineEvent(event as RawEvent | TimelineEvent)

        // Add to beginning and trim to max
        const events = [transformedEvent, ...state.timeline.events].slice(
          0,
          state.timeline.maxEvents,
        )

        return {
          timeline: {
            ...state.timeline,
            events,
            latestEvent: transformedEvent,
            lastPushTime: Date.now(),
          },
        }
      })
    },

    syncTimeline: (events) => {
      set((state) => {
        // Transform all events and slice to max
        const rawEvents = Array.isArray(events) ? events : [events]
        const transformedEvents = rawEvents
          .map((e) => transformTimelineEvent(e as RawEvent | TimelineEvent))
          .slice(0, state.timeline.maxEvents)

        return {
          timeline: {
            ...state.timeline,
            events: transformedEvents,
            latestEvent: transformedEvents[0] || null,
          },
        }
      })
    },

    clearTimeline: () => {
      set((state) => ({
        timeline: {
          ...state.timeline,
          events: [],
          latestEvent: null,
        },
      }))
    },

    setTimelineMaxEvents: (max) => {
      set((state) => ({
        timeline: {
          ...state.timeline,
          maxEvents: max,
          events: state.timeline.events.slice(0, max),
        },
      }))
    },

    holdTimelineEvent: (event) => {
      set((state) => {
        const pendingEvents = new Map(state.timeline.pendingEvents)
        pendingEvents.set(event.id, event)
        return {
          timeline: {
            ...state.timeline,
            pendingEvents,
            lastPushTime: Date.now(), // Update lastPushTime to trigger timeline visibility
          },
        }
      })
    },

    releaseTimelineEvent: (eventId) => {
      set((state) => {
        const pendingEvents = new Map(state.timeline.pendingEvents)
        const event = pendingEvents.get(eventId)

        if (!event) return state

        pendingEvents.delete(eventId)

        // Add the released event to the timeline
        const transformedEvent = transformTimelineEvent(event as RawEvent | TimelineEvent)
        const events = [transformedEvent, ...state.timeline.events].slice(
          0,
          state.timeline.maxEvents,
        )

        return {
          timeline: {
            ...state.timeline,
            events,
            latestEvent: transformedEvent,
            lastPushTime: Date.now(),
            pendingEvents,
          },
        }
      })
    },

    hasAlertWithId: (eventId) => {
      const state = get()
      // Check if alert with this ID is in queue or current
      return (
        state.alerts.currentAlert?.id === eventId ||
        state.alerts.queue.some((alert) => alert.id === eventId)
      )
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
  })),
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
  useRealtimeStore.getState().setConnectionStatus(connected, serverConnection.getConnectionState())
})

// Ensure connection is established
if (serverConnection.getConnectionState() === ConnectionState.Disconnected) {
  serverConnection.connect()
}
