import { useEffect, useState } from 'react'
import { useServer } from './use-server'

interface StreamStatus {
  status: 'online' | 'away' | 'busy' | 'brb' | 'focus'
  message: string
  updated_at: string | null
}

export function useStatus() {
  const [status, setStatus] = useState<StreamStatus>({
    status: 'online',
    message: '',
    updated_at: null,
  })

  const { data, isConnected } = useServer(['status:sync', 'status:update'] as const)

  useEffect(() => {
    // Handle initial sync
    const syncData = data['status:sync']
    if (syncData) {
      setStatus(syncData)
    }
  }, [data])

  useEffect(() => {
    // Handle status updates
    const updateData = data['status:update']
    if (updateData) {
      setStatus(updateData)
    }
  }, [data])

  return {
    status,
    isConnected,
  }
}