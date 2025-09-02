import { useState, useEffect } from 'react'

import { useServer } from '@/hooks/use-server'

const MESSAGE_TYPES = ['alerts:sync', 'alerts:push'] as const

interface Alert {
  id: string
  type: string
  message?: string
  [key: string]: unknown
}

export const Alerts = () => {
  const { data } = useServer(MESSAGE_TYPES)
  const [alertQueue, setAlertQueue] = useState<Alert[]>([])

  const alertsPush = data['alerts:push']
  const alertsSync = data['alerts:sync']

  useEffect(() => {
    if (alertsSync) {
      const alerts: Alert[] = Array.isArray(alertsSync) ? alertsSync : [alertsSync]
      setAlertQueue(alerts)
    }
  }, [alertsSync])

  useEffect(() => {
    if (alertsPush) {
      setAlertQueue((prev) => [...prev, alertsPush as Alert])
    }
  }, [alertsPush])

  return (
    <div>
      <div>
        Alert Queue ({alertQueue.length}): <pre>{JSON.stringify(alertQueue, null, 2)}</pre>
      </div>
    </div>
  )
}
