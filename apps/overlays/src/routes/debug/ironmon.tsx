import { createFileRoute } from '@tanstack/react-router'
import { useServer } from '@/hooks/use-server'
import { useState, useEffect, useRef } from 'react'

export const Route = createFileRoute('/debug/ironmon')({
  component: IronMONDebug,
})

function IronMONDebug() {
  const { data, isConnected } = useServer([
    'ironmon:init',
    'ironmon:seed',
    'ironmon:checkpoint',
    'ironmon:location',
    'ironmon:battle_started',
    'ironmon:battle_ended',
    'ironmon:team_update',
    'ironmon:item_usage',
    'ironmon:healing_summary',
    'ironmon:trainer_defeated',
    'ironmon:encounter',
    'ironmon:battle_damage',
    'ironmon:move_history',
    'ironmon:move_effectiveness',
    'ironmon:reset',
    'ironmon:error',
  ] as const)
  const [events, setEvents] = useState<Array<{ type: string; data: any; timestamp: string }>>([])
  const previousValuesRef = useRef<Map<string, string>>(new Map())

  // Capture IronMON events only when they actually change
  useEffect(() => {
    const keys = Object.keys(data) as Array<keyof typeof data>
    keys.forEach((key) => {
      if (key.startsWith('ironmon:') && data[key]) {
        const currentValue = JSON.stringify(data[key])
        const previousValue = previousValuesRef.current.get(key)

        // Only add if this specific message type's data has changed
        if (previousValue !== currentValue) {
          const timestamp = new Date().toLocaleTimeString()
          setEvents((prev) => [
            { type: key, data: data[key], timestamp },
            ...prev.slice(0, 49), // Keep last 50 events
          ])
          previousValuesRef.current.set(key, currentValue)
        }
      }
    })
  }, [data])

  return (
    <div className="min-h-screen bg-black text-green-500 p-8 font-mono text-sm">
      <h1 className="text-2xl mb-4 border-b-2 border-green-500 pb-2">IronMON Events Debug</h1>

      <div className="mb-4">
        <span className={`px-3 py-1 rounded ${isConnected ? 'bg-green-600' : 'bg-red-600'} text-white`}>
          {isConnected ? '✓ Connected' : '✗ Disconnected'}
        </span>
      </div>

      <div className="space-y-3">
        {events.length === 0 ? (
          <p className="text-gray-500">Waiting for IronMON events... Start a run in BizHawk!</p>
        ) : (
          events.map((event, i) => (
            <div key={i} className="border border-gray-700 bg-gray-900 p-4 rounded border-l-4 border-l-green-500">
              <div className="flex justify-between items-center mb-2">
                <span className="text-cyan-400 font-bold">{event.type}</span>
                <span className="text-gray-500 text-xs">{event.timestamp}</span>
              </div>
              <details>
                <summary className="cursor-pointer hover:underline text-yellow-400">
                  Show data
                </summary>
                <pre className="mt-2 p-2 bg-black rounded overflow-auto text-xs">
                  {JSON.stringify(event.data, null, 2)}
                </pre>
              </details>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
