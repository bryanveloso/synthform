import { createFileRoute } from '@tanstack/react-router'
import { useRealtimeStore } from '@/store/realtime'
import { serverConnection } from '@/hooks/use-server'
import { useState, useEffect, useRef, useCallback } from 'react'
import type { MessageType } from '@/types/server'

export const Route = createFileRoute('/debug/server')({
  component: ServerDebug,
})

// All message types we want to monitor (core overlay functionality).
// Game-specific types (ironmon, ffbot) are excluded — they have their own debug pages.
const MONITORED_TYPES: MessageType[] = [
  'base:sync',
  'base:update',
  'timeline:sync',
  'timeline:push',
  'ticker:sync',
  'alerts:sync',
  'alerts:push',
  'limitbreak:sync',
  'limitbreak:update',
  'limitbreak:executed',
  'status:sync',
  'status:update',
  'stream:sync',
  'stream:update',
  'obs:sync',
  'obs:update',
  'chat:sync',
  'chat:message',
  'campaign:sync',
  'campaign:update',
  'campaign:milestone',
  'campaign:timer:started',
  'campaign:timer:paused',
  'campaign:timer:tick',
]

// Sync types that should arrive on connect
const EXPECTED_SYNCS = [
  'ticker:sync',
  'alerts:sync',
  'limitbreak:sync',
  'status:sync',
] as const

// Sync types that only arrive when data exists
const CONDITIONAL_SYNCS = [
  'base:sync',
  'timeline:sync',
  'stream:sync',
  'obs:sync',
  'chat:sync',
  'campaign:sync',
] as const

interface EventLogEntry {
  id: number
  type: string
  payload: unknown
  timestamp: string
  receivedAt: string
  sequence: number
}

// Color coding by event category
function getCategoryColor(type: string): string {
  if (type.startsWith('base:')) return 'text-blue-400'
  if (type.startsWith('timeline:')) return 'text-purple-400'
  if (type.startsWith('ticker:')) return 'text-gray-400'
  if (type.startsWith('alerts:')) return 'text-red-400'
  if (type.startsWith('limitbreak:')) return 'text-yellow-400'
  if (type.startsWith('status:')) return 'text-green-400'
  if (type.startsWith('stream:')) return 'text-cyan-400'
  if (type.startsWith('obs:')) return 'text-orange-400'
  if (type.startsWith('chat:')) return 'text-pink-400'
  if (type.startsWith('campaign:')) return 'text-emerald-400'
  return 'text-white'
}

function getCategoryBorder(type: string): string {
  if (type.startsWith('base:')) return 'border-l-blue-400'
  if (type.startsWith('timeline:')) return 'border-l-purple-400'
  if (type.startsWith('ticker:')) return 'border-l-gray-400'
  if (type.startsWith('alerts:')) return 'border-l-red-400'
  if (type.startsWith('limitbreak:')) return 'border-l-yellow-400'
  if (type.startsWith('status:')) return 'border-l-green-400'
  if (type.startsWith('stream:')) return 'border-l-cyan-400'
  if (type.startsWith('obs:')) return 'border-l-orange-400'
  if (type.startsWith('chat:')) return 'border-l-pink-400'
  if (type.startsWith('campaign:')) return 'border-l-emerald-400'
  return 'border-l-white'
}

function ServerDebug() {
  const isConnected = useRealtimeStore((s) => s.isConnected)
  const status = useRealtimeStore((s) => s.status)
  const stream = useRealtimeStore((s) => s.stream)
  const limitbreak = useRealtimeStore((s) => s.limitbreak)

  const [events, setEvents] = useState<EventLogEntry[]>([])
  const [receivedSyncs, setReceivedSyncs] = useState<Set<string>>(new Set())
  const [connectedAt, setConnectedAt] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>('')
  const eventIdRef = useRef(0)
  const feedRef = useRef<HTMLDivElement>(null)

  // Track connection time
  useEffect(() => {
    if (isConnected) {
      setConnectedAt(new Date().toLocaleTimeString())
    } else {
      setConnectedAt(null)
      setReceivedSyncs(new Set())
    }
  }, [isConnected])

  // Stable callback for event logging
  const handleMessage = useCallback((messageType: string, payload: unknown) => {
    const now = new Date()
    eventIdRef.current += 1
    const id = eventIdRef.current
    setEvents((prev) => [
      {
        id,
        type: messageType,
        payload,
        timestamp: now.toISOString(),
        receivedAt: now.toLocaleTimeString('en-US', { hour12: false, fractionalSecondDigits: 3 }),
        sequence: id,
      },
      ...prev.slice(0, 199), // Keep last 200 events
    ])

    if (messageType.endsWith(':sync')) {
      setReceivedSyncs((prev) => new Set([...prev, messageType]))
    }
  }, [])

  // Subscribe directly to serverConnection for event logging
  useEffect(() => {
    const callbacks = new Map<MessageType, (data: unknown) => void>()

    MONITORED_TYPES.forEach((messageType) => {
      const callback = (data: unknown) => handleMessage(messageType, data)
      callbacks.set(messageType, callback)
      serverConnection.subscribe(messageType, callback as any)
    })

    return () => {
      callbacks.forEach((callback, messageType) => {
        serverConnection.unsubscribe(messageType, callback as any)
      })
    }
  }, [handleMessage])

  const filteredEvents = filter
    ? events.filter((e) => e.type.includes(filter))
    : events

  const chatCount = events.filter((e) => e.type === 'chat:message').length
  const alertCount = events.filter((e) => e.type === 'alerts:push').length
  const timelineCount = events.filter((e) => e.type === 'timeline:push').length

  return (
    <div className="min-h-screen bg-black text-white p-6 font-mono text-xs">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl mb-1 text-chalk">Synthform Server Debug</h1>
        <p className="text-gray-500">Monitoring WebSocket connection to Synthfunc</p>
      </div>

      {/* Connection Status */}
      <div className="mb-6 flex items-center gap-4">
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded ${
          isConnected ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'
        }`}>
          <span className={`inline-block h-2 w-2 rounded-full ${
            isConnected ? 'bg-green-400' : 'bg-red-400 animate-pulse'
          }`} />
          {isConnected ? 'Connected' : 'Disconnected'}
        </div>
        {connectedAt && (
          <span className="text-gray-500">Connected at {connectedAt}</span>
        )}
        <span className="text-gray-600">
          {events.length} events captured
        </span>
      </div>

      <div className="grid grid-cols-[320px_1fr] gap-6">
        {/* Left column: Sync checklist + Stats */}
        <div className="space-y-6">
          {/* Sync Checklist */}
          <div className="border border-gray-800 rounded p-4 bg-gray-950">
            <h2 className="text-sm font-bold mb-3 text-gray-300">Initial Sync Checklist</h2>

            <div className="mb-3">
              <h3 className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Required</h3>
              {EXPECTED_SYNCS.map((sync) => (
                <div key={sync} className="flex items-center gap-2 py-0.5">
                  <span className={receivedSyncs.has(sync) ? 'text-green-400' : 'text-gray-600'}>
                    {receivedSyncs.has(sync) ? '[ok]' : '[  ]'}
                  </span>
                  <span className={receivedSyncs.has(sync) ? 'text-white' : 'text-gray-500'}>
                    {sync}
                  </span>
                </div>
              ))}
            </div>

            <div>
              <h3 className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">Conditional (need data)</h3>
              {CONDITIONAL_SYNCS.map((sync) => (
                <div key={sync} className="flex items-center gap-2 py-0.5">
                  <span className={receivedSyncs.has(sync) ? 'text-green-400' : 'text-gray-600'}>
                    {receivedSyncs.has(sync) ? '[ok]' : '[--]'}
                  </span>
                  <span className={receivedSyncs.has(sync) ? 'text-white' : 'text-gray-600'}>
                    {sync}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Live Counters */}
          <div className="border border-gray-800 rounded p-4 bg-gray-950">
            <h2 className="text-sm font-bold mb-3 text-gray-300">Live Counters</h2>
            <div className="space-y-1">
              <div className="flex justify-between">
                <span className="text-pink-400">chat:message</span>
                <span className="text-white">{chatCount}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-red-400">alerts:push</span>
                <span className="text-white">{alertCount}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-purple-400">timeline:push</span>
                <span className="text-white">{timelineCount}</span>
              </div>
            </div>
          </div>

          {/* Current State Snapshot */}
          <div className="border border-gray-800 rounded p-4 bg-gray-950">
            <h2 className="text-sm font-bold mb-3 text-gray-300">Current State</h2>

            {/* Status */}
            {status && (
              <div className="mb-2">
                <span className="text-gray-500">Status: </span>
                <span className="text-green-400">
                  {status.status ?? '—'}
                </span>
              </div>
            )}

            {/* Stream Info */}
            {stream && (
              <div className="mb-2">
                <span className="text-gray-500">Stream: </span>
                <span className="text-cyan-400 break-words">
                  {stream.title ?? '—'}
                </span>
              </div>
            )}

            {/* Limit Break */}
            {limitbreak && (
              <div className="mb-2">
                <span className="text-gray-500">LB: </span>
                <span className="text-yellow-400">
                  {limitbreak.count ?? 0} redeems
                  {limitbreak.isMaxed && ' (MAXED)'}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Right column: Event Feed */}
        <div className="border border-gray-800 rounded bg-gray-950 flex flex-col max-h-[calc(100vh-180px)]">
          {/* Filter Bar */}
          <div className="flex items-center gap-2 p-3 border-b border-gray-800">
            <span className="text-gray-500">Filter:</span>
            <input
              type="text"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="e.g. chat, alerts, timeline..."
              className="flex-1 bg-black border border-gray-700 rounded px-2 py-1 text-white placeholder-gray-600 focus:border-gray-500 focus:outline-none"
            />
            {filter && (
              <button
                onClick={() => setFilter('')}
                className="text-gray-500 hover:text-white px-2"
              >
                clear
              </button>
            )}
            <button
              onClick={() => { setEvents([]); eventIdRef.current = 0 }}
              className="text-red-400 hover:text-red-300 px-2"
            >
              clear log
            </button>
          </div>

          {/* Event List */}
          <div ref={feedRef} className="flex-1 overflow-y-auto p-2 space-y-1">
            {filteredEvents.length === 0 ? (
              <p className="text-gray-600 p-4 text-center">
                {isConnected ? 'Waiting for events...' : 'Not connected'}
              </p>
            ) : (
              filteredEvents.map((event) => (
                <details
                  key={event.id}
                  className={`border border-gray-800 bg-gray-900/50 rounded border-l-2 ${getCategoryBorder(event.type)}`}
                >
                  <summary className="cursor-pointer px-3 py-1.5 flex items-center gap-3 hover:bg-gray-800/50">
                    <span className="text-gray-600 w-20 shrink-0">{event.receivedAt}</span>
                    <span className={`font-bold ${getCategoryColor(event.type)}`}>{event.type}</span>
                    <span className="text-gray-600 ml-auto">
                      {event.type === 'chat:message' && (
                        <span className="text-pink-300">
                          {(event.payload as { user_name?: string })?.user_name}: {(event.payload as { text?: string })?.text?.slice(0, 60)}
                        </span>
                      )}
                      {event.type === 'alerts:push' && (
                        <span className="text-red-300">
                          {(event.payload as { type?: string })?.type} — {(event.payload as { user_name?: string })?.user_name}
                        </span>
                      )}
                      {event.type === 'base:update' && (
                        <span className="text-blue-300">
                          {(event.payload as { data?: { user_name?: string } })?.data?.user_name}
                        </span>
                      )}
                      {event.type === 'status:update' && (
                        <span className="text-green-300">
                          {(event.payload as { status?: string })?.status}
                        </span>
                      )}
                      {event.type === 'stream:update' && (
                        <span className="text-cyan-300">
                          {(event.payload as { category_name?: string })?.category_name}
                        </span>
                      )}
                    </span>
                  </summary>
                  <pre className="px-3 py-2 bg-black/50 overflow-auto text-[10px] max-h-48 text-gray-400">
                    {JSON.stringify(event.payload, null, 2)}
                  </pre>
                </details>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
