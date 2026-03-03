import { createFileRoute } from '@tanstack/react-router'
import { useServer } from '@/hooks/use-server'
import { useIronMONStats, useIronMONRuns } from '@/hooks/use-questlog'
import { useState, useEffect, useRef } from 'react'

export const Route = createFileRoute('/debug/ironmon')({
  component: IronMONDebug,
})

function IronMONDebug() {
  const { data: stats, isLoading: statsLoading } = useIronMONStats('kaizo')
  const { data: runs, isLoading: runsLoading } = useIronMONRuns('kaizo', 20)

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
    'ironmon:battle_action',
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

      {/* Stats from Questlog */}
      <div className="mb-6 border border-gray-700 bg-gray-900 p-4 rounded">
        <h2 className="text-lg text-cyan-400 mb-3">Stats (Questlog)</h2>
        {statsLoading ? (
          <p className="text-gray-500">Loading stats...</p>
        ) : stats ? (
          <div>
            <div className="grid grid-cols-4 gap-4 mb-4">
              <div>
                <span className="text-gray-500">Challenge</span>
                <p className="text-white">{stats.challenge}</p>
              </div>
              <div>
                <span className="text-gray-500">Total Runs</span>
                <p className="text-white">{stats.total_runs}</p>
              </div>
              <div>
                <span className="text-gray-500">Victories</span>
                <p className="text-white">{stats.victories}</p>
              </div>
              <div>
                <span className="text-gray-500">Runs w/ Checkpoints</span>
                <p className="text-white">{stats.runs_with_results}</p>
              </div>
            </div>
            {stats.checkpoints.length > 0 && (
              <details>
                <summary className="cursor-pointer hover:underline text-yellow-400">
                  Checkpoint Clear Rates
                </summary>
                <table className="mt-2 w-full text-xs">
                  <thead>
                    <tr className="text-gray-500 text-left">
                      <th className="pr-4">#</th>
                      <th className="pr-4">Checkpoint</th>
                      <th className="pr-4">Trainer</th>
                      <th className="pr-4">Entered</th>
                      <th className="pr-4">Survived</th>
                      <th>Survival Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.checkpoints.map((cp) => (
                      <tr key={cp.order} className="text-gray-300">
                        <td className="pr-4">{cp.order}</td>
                        <td className="pr-4">{cp.name}</td>
                        <td className="pr-4">{cp.trainer}</td>
                        <td className="pr-4">{cp.entered}</td>
                        <td className="pr-4">{cp.survived}</td>
                        <td>{(cp.survival_rate * 100).toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            )}
          </div>
        ) : (
          <p className="text-red-400">Failed to load stats</p>
        )}
      </div>

      {/* Recent Runs from Questlog */}
      <div className="mb-6 border border-gray-700 bg-gray-900 p-4 rounded">
        <h2 className="text-lg text-cyan-400 mb-3">Recent Runs (Questlog)</h2>
        {runsLoading ? (
          <p className="text-gray-500">Loading runs...</p>
        ) : runs ? (
          <div>
            <p className="text-gray-500 mb-2">{runs.total} total runs</p>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-500 text-left">
                  <th className="pr-4">Seed</th>
                  <th className="pr-4">Highest Checkpoint</th>
                  <th className="pr-4">Victory</th>
                  <th>Started</th>
                </tr>
              </thead>
              <tbody>
                {runs.runs.map((run) => (
                  <tr key={run.seed_number} className="text-gray-300">
                    <td className="pr-4">{run.seed_number}</td>
                    <td className="pr-4">{run.highest_checkpoint || '-'}</td>
                    <td className="pr-4">{run.is_victory ? '✓' : '-'}</td>
                    <td>{new Date(run.started_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-red-400">Failed to load runs</p>
        )}
      </div>

      {/* Live Event Log */}
      <h2 className="text-lg text-cyan-400 mb-3">Live Events (WebSocket)</h2>
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
