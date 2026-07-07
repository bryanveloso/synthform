/* eslint-disable @typescript-eslint/no-explicit-any */
import type { TimelineEvent } from '@/types/events'

// Raw event interface for transformation
export interface RawEvent {
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

// Transform raw events to TimelineEvent format.
//
// Pure — no store, no transport, no side effects — so it can be unit-tested in
// isolation. This is the single place the Redis→WebSocket envelope is normalized
// (`event_type || type`, notice_type mapping); keeping it in one tested place is
// what prevents the field ambiguity from silently regressing across consumers.
export function transformTimelineEvent(rawEvent: RawEvent): TimelineEvent {
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
