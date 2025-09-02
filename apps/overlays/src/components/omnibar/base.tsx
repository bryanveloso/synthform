import { useState, useEffect } from 'react'

import { useServer } from '@/hooks/use-server'

const MESSAGE_TYPES = ['base:sync', 'base:update'] as const

interface TimelineEvent {
  id: string
  timestamp: string
  type: string
  [key: string]: unknown
}

export const Base = () => {
  const { data } = useServer(MESSAGE_TYPES)
  const [baseData, setBaseData] = useState<TimelineEvent | null>(null)

  const baseSync = data['base:sync']
  const baseUpdate = data['base:update']

  useEffect(() => {
    if (baseSync) {
      setBaseData(baseSync)
    }
  }, [baseSync])

  useEffect(() => {
    if (baseUpdate) {
      setBaseData(baseUpdate)
    }
  }, [baseUpdate])

  return (
    <div>
      <div>
        Base Data: <pre>{baseData ? JSON.stringify(baseData, null, 2) : 'No data'}</pre>
      </div>
    </div>
  )
}
