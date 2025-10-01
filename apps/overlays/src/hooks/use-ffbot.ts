import { useMemo, useRef, useState, useEffect } from 'react'
import { useRealtimeStore } from '@/store/realtime'

export interface FFBotEvent {
  id: string
  timestamp: string
  type:
    | 'stats'
    | 'hire'
    | 'change'
    | 'attack'
    | 'join'
    | 'preference'
    | 'ascension_preview'
    | 'ascension_confirm'
    | 'esper'
    | 'artifact'
    | 'job'
    | 'card'
    | 'mastery'
    | 'freehire'
    | 'missing'
    | 'party_wipe'
    | 'new_run'
    | 'battle_victory'
    | 'save'
  player: string
  displayName: string
  message: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  metadata?: Record<string, any>
}

interface UseFFBotOptions {
  maxEvents?: number
  enableActivityTracking?: boolean
}

export function useFFBot(options: UseFFBotOptions = {}) {
  const { maxEvents = 100, enableActivityTracking = true } = options

  // Get raw FFBot events from the store
  const rawEvents = useRealtimeStore((state) => state.ffbot.events)
  const isConnected = useRealtimeStore((state) => state.isConnected)

  // Track when new events arrive
  const prevEventCount = useRef(rawEvents.length)
  const [hasJustReceivedEvent, setHasJustReceivedEvent] = useState(false)

  useEffect(() => {
    if (rawEvents.length > prevEventCount.current) {
      setHasJustReceivedEvent(true)
      const timeout = setTimeout(() => setHasJustReceivedEvent(false), 1000)
      prevEventCount.current = rawEvents.length
      return () => clearTimeout(timeout)
    }
    prevEventCount.current = rawEvents.length
  }, [rawEvents.length])

  // Transform and limit events with useMemo to avoid re-renders
  const events = useMemo(() => {
    return rawEvents
      .map((event) => {
        // FFBot events already include an explicit 'type' field - use it directly
        const type = (event.type as FFBotEvent['type']) || 'stats'

        const player = 'player' in event ? event.player : 'System'
        const displayName = 'member' in event && event.member ? event.member.display_name : player

        return {
          id: `ffbot-${event.timestamp}-${Math.random().toString(36).substring(2, 9)}`,
          timestamp: event.timestamp,
          type,
          player: player.toLowerCase(),
          displayName,
          message: formatFFBotMessage(type, event),
          metadata: event,
        }
      })
      .slice(-maxEvents)
  }, [rawEvents, maxEvents])

  // Computed values
  const latestEvent = useMemo(() => {
    return events[events.length - 1] || null
  }, [events])

  const playerActivity = useMemo(() => {
    if (!enableActivityTracking) return {}

    return events.reduce(
      (acc, event) => {
        acc[event.player] = (acc[event.player] || 0) + 1
        return acc
      },
      {} as Record<string, number>,
    )
  }, [events, enableActivityTracking])

  const eventTypeCounts = useMemo(() => {
    if (!enableActivityTracking) return {}

    return events.reduce(
      (acc, event) => {
        acc[event.type] = (acc[event.type] || 0) + 1
        return acc
      },
      {} as Record<string, number>,
    )
  }, [events, enableActivityTracking])

  const activePlayers = useMemo(() => {
    return Object.keys(playerActivity).sort()
  }, [playerActivity])

  const mostActivePlayer = useMemo(() => {
    const entries = Object.entries(playerActivity)
    if (entries.length === 0) return null

    return entries.reduce(
      (max, [player, count]) => (count > (max?.count || 0) ? { player, count } : max),
      null as { player: string; count: number } | null,
    )
  }, [playerActivity])

  const recentPlayers = useMemo(() => {
    const recent = events.slice(-10)
    return [...new Set(recent.map((e) => e.displayName))]
  }, [events])

  const eventsByType = useMemo(() => {
    return events.reduce(
      (acc, event) => {
        if (!acc[event.type]) acc[event.type] = []
        acc[event.type].push(event)
        return acc
      },
      {} as Record<FFBotEvent['type'], FFBotEvent[]>,
    )
  }, [events])

  // Return semantic API
  return {
    // Raw data
    events,
    latestEvent,

    // Activity tracking
    playerActivity,
    eventTypeCounts,
    activePlayers,
    activePlayerCount: activePlayers.length,
    mostActivePlayer,
    recentPlayers,
    eventsByType,

    // State flags
    isEmpty: events.length === 0,
    isFull: events.length >= maxEvents,
    hasJustReceivedEvent,
    isConnected,

    // Metadata
    eventCount: events.length,
    maxEvents,
    lastEventTime: latestEvent?.timestamp || null,

    // Methods
    // TODO: Implement these methods in useRealtimeStore
    // These require adding corresponding actions to clear ffbot.events array
    clearEvents: () => {
      console.warn('clearEvents not implemented in store yet')
    },
    clearActivity: () => {
      console.warn('clearActivity not implemented in store yet')
    },
  }
}

// Helper function to format FFBot messages (extracted from original hook)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function formatFFBotMessage(type: string, payload: Record<string, any>): string {
  switch (type) {
    case 'stats': {
      const data = 'data' in payload ? payload.data : payload
      const stats = []
      if (data?.hp) stats.push(`HP:${data.hp}`)
      if (data?.atk) stats.push(`ATK:${data.atk}`)
      if (data?.mag) stats.push(`MAG:${data.mag}`)
      if (data?.spi) stats.push(`SPI:${data.spi}`)
      const statsStr = stats.length > 0 ? ` [${stats.join(' ')}]` : ''
      return `checked stats (Lv${data?.lv || '?'} ${data?.unit || 'Unknown'})${statsStr}`
    }

    case 'hire': {
      const cost = payload?.cost ? ` for ${payload.cost} gil` : ''
      const data = 'data' in payload ? payload.data : {}
      const collection = data?.collection ? ` (${data.collection} collected)` : ''
      return `hired ${payload?.character || 'a new unit'}${cost}${collection}`
    }

    case 'change':
      return `changed to ${payload?.to || 'a different character'}`

    case 'preference':
      return `set stat preference to ${payload?.preference || 'none'}`

    case 'ascension_preview':
      return `previewing ascension (Level ${payload?.current_ascension || 0})`

    case 'ascension_confirm':
      return `ascended to Level ${payload?.ascension || 0}! 🌟`

    case 'esper':
      return `equipped ${payload?.esper || 'an esper'}`

    case 'artifact': {
      const bonuses = []
      if (payload?.bonuses?.hp) bonuses.push(`HP+${payload.bonuses.hp}`)
      if (payload?.bonuses?.atk) bonuses.push(`ATK+${payload.bonuses.atk}`)
      if (payload?.bonuses?.mag) bonuses.push(`MAG+${payload.bonuses.mag}`)
      if (payload?.bonuses?.spi) bonuses.push(`SPI+${payload.bonuses.spi}`)
      const bonusStr = bonuses.length > 0 ? ` [${bonuses.join(' ')}]` : ''
      return `equipped artifact ${payload?.artifact || 'unknown'}${bonusStr}`
    }

    case 'job':
      return `changed job to ${payload?.job || 'unknown'}`

    case 'card': {
      const passive = payload?.passive ? ` (${payload.passive})` : ''
      return `equipped ${payload?.card || 'a card'}${passive}`
    }

    case 'mastery':
      if (payload?.success) {
        return `mastered ${payload?.job || 'a job'} in slot ${payload?.slot || '?'}`
      } else {
        return `failed to master ${payload?.job || 'a job'} (need Lv${payload?.required_level || '?'})`
      }

    case 'freehire':
      if (payload?.available) {
        return `used free hire on ${payload?.character || 'a character'}`
      } else {
        return `free hire not available yet`
      }

    case 'missing': {
      const count = payload?.missing?.length || 0
      return `missing ${count} character${count !== 1 ? 's' : ''} from collection`
    }

    case 'attack': {
      const damage = payload?.damage || '???'
      const target = payload?.target || 'an enemy'
      const critical = payload?.critical ? ' 💥 CRITICAL!' : ''
      return `attacked ${target} for ${damage} damage${critical}`
    }

    case 'join':
      return `joined the game!`

    case 'party_wipe':
      return `💀 Party wiped on Cycle ${payload?.cycle || '?'} (${payload?.pity_remaining || 0} attempts until pity)`

    case 'new_run':
      return `🎮 New run started: Cycle ${payload?.cycle || '?'} Stage ${payload?.stage || '?'}`

    case 'battle_victory': {
      const bossStr = payload?.boss_defeated ? ' (BOSS DEFEATED!)' : ''
      return `✨ Victory at Stage ${payload?.stage || '?'}${bossStr}`
    }

    case 'save':
      return `💾 Game progress saved!`

    default:
      return type
  }
}
