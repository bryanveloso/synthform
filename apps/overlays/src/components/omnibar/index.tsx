import { useServer } from '@/hooks/use-server'
import { useState, useEffect } from 'react'

const MESSAGE_TYPES = ['base:sync', 'base:update', 'timeline:sync', 'timeline:push', 'alerts:sync', 'alerts:push'] as const

interface TimelineEvent {
  id: string
  timestamp: string
  type: string
  [key: string]: unknown
}

interface Alert {
  id: string
  type: string
  message?: string
  [key: string]: unknown
}

export const Omnibar = () => {
  const { data, isConnected } = useServer(MESSAGE_TYPES)
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([])
  const [alertQueue, setAlertQueue] = useState<Alert[]>([])

  // Extract specific data values to avoid dependency issues
  const timelineSync = data['timeline:sync']
  const timelinePush = data['timeline:push']
  const alertsSync = data['alerts:sync']
  const alertsPush = data['alerts:push']

  // Initialize timeline with recent events from sync
  useEffect(() => {
    if (timelineSync) {
      const events: TimelineEvent[] = Array.isArray(timelineSync) ? timelineSync : [timelineSync]
      setTimelineEvents(events)
    }
  }, [timelineSync])

  // Append new events from push
  useEffect(() => {
    if (timelinePush) {
      setTimelineEvents(prev => [...prev, timelinePush as TimelineEvent])
    }
  }, [timelinePush])

  // Initialize alert queue from sync (should be empty)
  useEffect(() => {
    if (alertsSync) {
      const alerts: Alert[] = Array.isArray(alertsSync) ? alertsSync : [alertsSync]
      setAlertQueue(alerts)
    }
  }, [alertsSync])

  // Append new alerts from push
  useEffect(() => {
    if (alertsPush) {
      setAlertQueue(prev => [...prev, alertsPush as Alert])
    }
  }, [alertsPush])

  return (
    <div>
      <div>WebSocket: {isConnected ? 'Connected' : 'Disconnected'}</div>
      <div>
        Base Data: <pre>{data['base:sync'] ? JSON.stringify(data['base:sync'], null, 2) : 'No data'}</pre>
      </div>
      <div>
        Timeline Events ({timelineEvents.length}):{' '}
        <pre>{timelineEvents.length > 0 ? JSON.stringify(timelineEvents, null, 2) : 'No events'}</pre>
      </div>
      <div>
        Alert Queue ({alertQueue.length}):{' '}
        <pre>{JSON.stringify(alertQueue, null, 2)}</pre>
      </div>
    </div>
  )
}
