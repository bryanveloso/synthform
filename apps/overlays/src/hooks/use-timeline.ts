import { useState, useEffect } from 'react'
import { useServer } from './use-server'
import type { TimelineEvent } from '@/types/events'

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
  let eventType = rawEvent.event_type || rawEvent.type || ''

  // Handle consolidated chat.notification events from Twitch
  // These come through with a notice_type that tells us the real event type
  if (eventType === 'channel.chat.notification' && rawEvent.payload?.notice_type) {
    const noticeTypeMap: Record<string, string> = {
      'sub': 'channel.subscribe',
      'resub': 'channel.subscription.message',
      'sub_gift': 'channel.subscription.gift',
      'community_sub_gift': 'channel.subscription.gift',
      'gift_paid_upgrade': 'channel.subscription.gift',
      'prime_paid_upgrade': 'channel.subscribe',
      'raid': 'channel.raid',
      'unraid': 'channel.raid',
      'pay_it_forward': 'channel.subscription.gift',
      'announcement': 'channel.announcement',
      'bits_badge_tier': 'channel.cheer',
      'charity_donation': 'channel.charity_donation',
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

  const isStale = (event: TimelineEvent) => {
    const eventTime = new Date(event.data.timestamp).getTime()
    const ageInMs = Date.now() - eventTime
    const ageInHours = ageInMs / (1000 * 60 * 60)
    return ageInHours > 24
  }

  return {
    events,
    isConnected,
    isStale,
    // Expose utilities if needed
    clearEvents: () => setEvents([]),
    addTestEvent: (event: RawEvent) => {
      const transformed = transformEvent(event)
      setEvents((prev) => [transformed, ...prev].slice(0, maxEvents))
    },
  }
}
