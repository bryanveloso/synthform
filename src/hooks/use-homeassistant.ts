import { useEffect, useState } from 'react'
import { connectHomeAssistant } from '@/api/homeassistant'
import type { HassEntities } from '@/api/homeassistant'

export type { HassEntities }

export function useHomeAssistant() {
  const [entities, setEntities] = useState<HassEntities>({})
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let disconnect: (() => void) | undefined

    connectHomeAssistant({
      onEntities: setEntities,
      onConnected: () => { setIsConnected(true); setError(null) },
      onDisconnected: () => setIsConnected(false),
      onError: (err) => { setError(err); setIsConnected(false) },
    }).then((fn) => { disconnect = fn })

    return () => disconnect?.()
  }, [])

  return { entities, isConnected, error }
}
