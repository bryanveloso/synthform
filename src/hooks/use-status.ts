import { useEffect, useState } from 'react'
import { useServer } from './use-server'
import type { StreamStatus } from '@/types/server'

export function useStatus() {
  const [status, setStatus] = useState<StreamStatus>({
    status: 'online',
    message: '',
    updated_at: null,
  })

  const { data, isConnected } = useServer(['status:sync', 'status:update'] as const)

  const syncData = data['status:sync']
  const updateData = data['status:update']

  useEffect(() => {
    if (syncData) {
      setStatus(syncData)
    }
  }, [syncData])

  useEffect(() => {
    if (updateData) {
      setStatus(updateData)
    }
  }, [updateData])

  return {
    status,
    isConnected,
  }
}
