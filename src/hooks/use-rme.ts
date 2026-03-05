import { useRealtimeStore } from '@/store/realtime'

export interface RMEMicStatus {
  channel: number
  muted: boolean
  timestamp: string
}

export interface RMEState {
  mic: RMEMicStatus | null
  isConnected: boolean
}

export function useRME() {
  const mic = useRealtimeStore((s) => s.rme)
  const isConnected = useRealtimeStore((s) => s.isConnected)

  return {
    mic,
    isMuted: mic?.muted ?? false,
    isConnected,
  }
}

export function useMicStatus() {
  const { mic, isMuted, isConnected } = useRME()

  return {
    channel: mic?.channel ?? 0,
    isMuted,
    isConnected,
    timestamp: mic?.timestamp,
  }
}