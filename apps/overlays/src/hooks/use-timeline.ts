import { useState, useEffect } from 'react'

import type { TimelineEvent } from '@/types/events'

import { useServer } from './use-server'

const MESSAGE_TYPES = ['timeline:sync', 'timeline:push'] as const

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

function transformEvent(rawEvent: RawEvent): TimelineEvent {
  // If it already has the correct structure (from database), return as-is
  if (rawEvent.type && rawEvent.type.includes('.') && rawEvent.data) {
    return rawEvent as TimelineEvent
  }

  // Transform raw event from Redis
  const source = rawEvent.source || 'twitch'
  const eventType = rawEvent.event_type || rawEvent.type || ''

  return {
    id: rawEvent.event_id || rawEvent.id || `${Date.now()}`,
    type: `${source}.${eventType}` as any,
    data: {
      timestamp: rawEvent.timestamp || new Date().toISOString(),
      payload: rawEvent.payload || {},
      user_name: rawEvent.username || rawEvent.payload?.user_name || 'Unknown',
    },
  }
}

export function useTimeline(maxEvents: number = 10) {
  const { data, isConnected } = useServer(MESSAGE_TYPES)
  const [events, setEvents] = useState<TimelineEvent[]>([])

  const timelinePush = data['timeline:push']
  const timelineSync = data['timeline:sync']

  // Handle initial sync
  useEffect(() => {
    if (timelineSync) {
      const rawEvents = Array.isArray(timelineSync) ? timelineSync : [timelineSync]
      const transformedEvents = rawEvents.map(transformEvent)
      setEvents(transformedEvents.slice(0, maxEvents))
    }
  }, [timelineSync, maxEvents])

  // Handle new events
  useEffect(() => {
    if (timelinePush) {
      const event = transformEvent(timelinePush)
      setEvents((prev) => {
        const newEvents = [event, ...prev]
        return newEvents.slice(0, maxEvents)
      })
    }
  }, [timelinePush, maxEvents])

  return {
    events,
    isConnected,
    // Expose utilities if needed
    clearEvents: () => setEvents([]),
    addTestEvent: (event: RawEvent) => {
      const transformed = transformEvent(event)
      setEvents((prev) => [transformed, ...prev].slice(0, maxEvents))
    },
  }
}
