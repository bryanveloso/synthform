import { useRealtimeStore } from '@/store/realtime'

export function useStatus() {
  const status = useRealtimeStore((s) => s.status)
  const isConnected = useRealtimeStore((s) => s.isConnected)

  return {
    status: status ?? { status: 'online' as const, message: '', updated_at: null },
    isConnected,
  }
}
