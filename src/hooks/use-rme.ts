import { useEffect, useState } from 'react'
import { useServer } from './use-server'

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
  const [micStatus, setMicStatus] = useState<RMEMicStatus | null>(null)

  const { data, isConnected } = useServer(['audio:rme:status', 'audio:rme:update'] as const)

  const syncData = data['audio:rme:status']
  const updateData = data['audio:rme:update']

  useEffect(() => {
    if (syncData) {
      setMicStatus(syncData)
    }
  }, [syncData])

  useEffect(() => {
    if (updateData) {
      setMicStatus(updateData)
    }
  }, [updateData])

  return {
    mic: micStatus,
    isMuted: micStatus?.muted ?? false,
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