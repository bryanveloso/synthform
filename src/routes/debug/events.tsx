import { createFileRoute } from '@tanstack/react-router'
import { useRealtimeStore } from '@/store/realtime'

export const Route = createFileRoute('/debug/events')({
  component: DebugTimeline,
})

function DebugTimeline() {
  const events = useRealtimeStore((s) => s.timeline.events)
  const isConnected = useRealtimeStore((s) => s.isConnected)

  return (
    <div className="min-h-screen bg-black text-white p-8 font-mono text-xs">
      <h1 className="text-2xl mb-4">Timeline Debug</h1>

      <div className="mb-4">
        <span className={`px-2 py-1 rounded ${isConnected ? 'bg-green-600' : 'bg-red-600'}`}>
          {isConnected ? 'Connected' : 'Disconnected'}
        </span>
      </div>

      <div className="mb-8">
        <h2 className="text-xl mb-2">Timeline Events</h2>
        {events.length > 0 ? (
          <div>
            <p className="mb-2">{events.length} events</p>

            <div className="mb-4">
              <h3 className="text-lg mb-2">Event Types:</h3>
              <ul className="list-disc list-inside">
                {events.map((event, i) => (
                  <li key={i}>
                    {event.type} - ID: {event.id} - User: {event.data?.user_name || 'Unknown'}
                  </li>
                ))}
              </ul>
            </div>

            <div className="mb-4">
              <h3 className="text-lg mb-2">Events with channel.chat.notification:</h3>
              <ul className="list-disc list-inside">
                {events
                  .filter((event) => event.type?.includes('channel.chat.notification'))
                  .map((event, i) => (
                    <li key={i}>
                      {event.type} - notice_type: {event.data?.payload?.notice_type || 'N/A'}
                    </li>
                  ))}
              </ul>
              {events.filter((event) => event.type?.includes('channel.chat.notification')).length === 0 && (
                <p className="text-red-500">No channel.chat.notification events found!</p>
              )}
            </div>

            <details className="mt-4">
              <summary className="cursor-pointer hover:underline">Raw JSON Data (click to expand)</summary>
              <pre className="mt-2 p-4 bg-gray-900 rounded overflow-auto max-h-96">
                {JSON.stringify(events, null, 2)}
              </pre>
            </details>
          </div>
        ) : (
          <p>Waiting for timeline events...</p>
        )}
      </div>
    </div>
  )
}