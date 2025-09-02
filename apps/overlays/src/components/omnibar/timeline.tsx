import { useState, useEffect } from 'react'

import { useServer } from '@/hooks/use-server'

const MESSAGE_TYPES = ['timeline:sync', 'timeline:push'] as const

interface TimelineEvent {
  id: string
  timestamp: string
  type: string
  [key: string]: unknown
}

export const Timeline = () => {
  const { data } = useServer(MESSAGE_TYPES)
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([])

  const timelinePush = data['timeline:push']
  const timelineSync = data['timeline:sync']

  useEffect(() => {
    if (timelineSync) {
      const events: TimelineEvent[] = Array.isArray(timelineSync) ? timelineSync : [timelineSync]
      setTimelineEvents(events)
    }
  }, [timelineSync])

  useEffect(() => {
    if (timelinePush) {
      setTimelineEvents((prev) => [timelinePush as TimelineEvent, ...prev])
    }
  }, [timelinePush])

  return (
    <div>
      <div>
        Timeline Events ({timelineEvents.length}):{' '}
        <pre>{timelineEvents.length > 0 ? JSON.stringify(timelineEvents, null, 2) : 'No events'}</pre>
      </div>
    </div>
  )
}
