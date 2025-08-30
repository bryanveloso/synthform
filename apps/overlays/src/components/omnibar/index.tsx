import { useServer } from '@/hooks/use-server'
import { useState, useEffect } from 'react'

const MESSAGE_TYPES = ['base:sync', 'base:update', 'timeline:sync', 'timeline:push', 'alerts:sync', 'alerts:push'] as const

export const Omnibar = () => {
  const { data, isConnected } = useServer(MESSAGE_TYPES)
  const [timelineEvents, setTimelineEvents] = useState<any[]>([])
  const [alertQueue, setAlertQueue] = useState<any[]>([])

  // Initialize timeline with recent events from sync
  useEffect(() => {
    if (data['timeline:sync']) {
      setTimelineEvents(Array.isArray(data['timeline:sync']) ? data['timeline:sync'] : [data['timeline:sync']])
    }
  }, [data['timeline:sync']])

  // Append new events from push
  useEffect(() => {
    if (data['timeline:push']) {
      setTimelineEvents(prev => [...prev, data['timeline:push']])
    }
  }, [data['timeline:push']])

  // Initialize alert queue from sync (should be empty)
  useEffect(() => {
    if (data['alerts:sync']) {
      setAlertQueue(Array.isArray(data['alerts:sync']) ? data['alerts:sync'] : [data['alerts:sync']])
    }
  }, [data['alerts:sync']])

  // Append new alerts from push
  useEffect(() => {
    if (data['alerts:push']) {
      setAlertQueue(prev => [...prev, data['alerts:push']])
    }
  }, [data['alerts:push']])

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
