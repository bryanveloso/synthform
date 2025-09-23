import { useCallback } from 'react'
import { useRealtimeStore } from '@/store/realtime'
import type { TimelineEvent } from '@/types/events'

/**
 * Hook for accessing timeline events from the Zustand store.
 * @param maxEvents - Maximum number of events to return (default: 10)
 */
export function useTimeline(maxEvents: number = 10) {
  const allEvents = useRealtimeStore((state) => state.timeline.events)
  const isConnected = useRealtimeStore((state) => state.isConnected)
  const clearTimeline = useRealtimeStore((state) => state.clearTimeline)
  const addTimelineEvent = useRealtimeStore((state) => state.addTimelineEvent)

  // Return only the requested number of events
  const events = allEvents.slice(0, maxEvents)

  // Utility to check if an event is stale
  const isStale = useCallback((event: TimelineEvent) => {
    const eventTime = new Date(event.data.timestamp).getTime()
    const ageInMs = Date.now() - eventTime
    const ageInHours = ageInMs / (1000 * 60 * 60)
    return ageInHours > 24
  }, [])

  // Test helper to add a test event
  const addTestEvent = useCallback(
    (event: TimelineEvent) => {
      addTimelineEvent(event)
    },
    [addTimelineEvent]
  )

  return {
    events,
    isConnected,
    isStale,
    clearEvents: clearTimeline,
    addTestEvent,
  }
}
