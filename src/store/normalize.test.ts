import { describe, expect, test } from 'bun:test'

import { transformTimelineEvent } from './normalize'

// Guards the Redis→WebSocket envelope normalization. The `event_type` field
// silently regressing to `type` once left synthhome overlays dead for ~2 months.
describe('transformTimelineEvent', () => {
  test('honors event_type from the Redis envelope', () => {
    const result = transformTimelineEvent({
      event_type: 'channel.follow',
      source: 'twitch',
      timestamp: '2026-01-01T00:00:00Z',
      payload: { user_name: 'alice' },
    })

    expect(result.type).toBe('twitch.channel.follow')
    expect(result.data.user_name).toBe('alice')
  })

  test('falls back to `type` when event_type is absent', () => {
    const result = transformTimelineEvent({
      type: 'channel.cheer',
      source: 'twitch',
      payload: {},
    })

    expect(result.type).toBe('twitch.channel.cheer')
  })

  test('passes through already-structured timeline events unchanged', () => {
    const structured = {
      id: 'abc',
      type: 'twitch.channel.subscribe',
      data: { timestamp: 't', payload: {}, user_name: 'bob' },
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(transformTimelineEvent(structured as any)).toBe(structured as any)
  })

  test('maps a chat.notification notice_type to its real event type', () => {
    const result = transformTimelineEvent({
      event_type: 'channel.chat.notification',
      source: 'twitch',
      payload: { notice_type: 'raid', user_name: 'carol' },
    })

    expect(result.type).toBe('twitch.channel.raid')
  })
})
