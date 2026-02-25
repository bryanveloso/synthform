import { useRealtimeStore } from '@/store/realtime'

/**
 * Shows a small red dot in the corner when disconnected from the server.
 * Invisible when connected - only appears when there's a problem.
 */
export function ConnectionAlert() {
  const isConnected = useRealtimeStore((state) => state.isConnected)

  // Don't render anything when connected
  if (isConnected) {
    return null
  }

  return (
    <div
      className="fixed top-4 right-4 z-[99999] h-3 w-3 animate-pulse rounded-full bg-red-500"
      title="Disconnected from server"
    />
  )
}
