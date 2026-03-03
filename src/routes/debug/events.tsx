import { createFileRoute } from '@tanstack/react-router'
import { useServer } from '@/hooks/use-server'
import { useEffect, useState } from 'react'

export const Route = createFileRoute('/debug/events')({
  component: DebugTimeline,
})

function DebugTimeline() {
  const { data, isConnected } = useServer(['timeline:sync', 'timeline:push'])
  const [syncData, setSyncData] = useState<any>(null)
  const [rawData, setRawData] = useState<any>(null)

  useEffect(() => {
    if (data['timeline:sync']) {
      setSyncData(data['timeline:sync'])
      setRawData(JSON.stringify(data['timeline:sync'], null, 2))
    }
  }, [data])

  return (
    <div className="min-h-screen bg-black text-white p-8 font-mono text-xs">
      <h1 className="text-2xl mb-4">Timeline Debug</h1>

      <div className="mb-4">
        <span className={`px-2 py-1 rounded ${isConnected ? 'bg-green-600' : 'bg-red-600'}`}>
          {isConnected ? 'Connected' : 'Disconnected'}
        </span>
      </div>

      <div className="mb-8">
        <h2 className="text-xl mb-2">Timeline Sync Data</h2>
        {syncData ? (
          <div>
            <p className="mb-2">Received {Array.isArray(syncData) ? syncData.length : 1} events</p>

            <div className="mb-4">
              <h3 className="text-lg mb-2">Event Types:</h3>
              <ul className="list-disc list-inside">
                {(Array.isArray(syncData) ? syncData : [syncData]).map((event: any, i: number) => (
                  <li key={i}>
                    {event.type} - ID: {event.id} - User: {event.data?.user_name || 'Unknown'}
                  </li>
                ))}
              </ul>
            </div>

            <div className="mb-4">
              <h3 className="text-lg mb-2">Events with channel.chat.notification:</h3>
              <ul className="list-disc list-inside">
                {(Array.isArray(syncData) ? syncData : [syncData])
                  .filter((event: any) => event.type?.includes('channel.chat.notification'))
                  .map((event: any, i: number) => (
                    <li key={i}>
                      {event.type} - notice_type: {event.data?.payload?.notice_type || 'N/A'}
                    </li>
                  ))}
              </ul>
              {(Array.isArray(syncData) ? syncData : [syncData])
                .filter((event: any) => event.type?.includes('channel.chat.notification')).length === 0 && (
                <p className="text-red-500">No channel.chat.notification events found!</p>
              )}
            </div>

            <details className="mt-4">
              <summary className="cursor-pointer hover:underline">Raw JSON Data (click to expand)</summary>
              <pre className="mt-2 p-4 bg-gray-900 rounded overflow-auto max-h-96">
                {rawData}
              </pre>
            </details>
          </div>
        ) : (
          <p>Waiting for timeline:sync data...</p>
        )}
      </div>
    </div>
  )
}