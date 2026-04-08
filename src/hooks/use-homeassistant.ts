import { useEffect, useRef, useState } from 'react'
import {
  createLongLivedTokenAuth,
  createConnection,
  subscribeEntities,
} from 'home-assistant-js-websocket'
import type { Connection, HassEntities } from 'home-assistant-js-websocket'

const HA_URL = import.meta.env.VITE_HOMEASSISTANT_URL || 'http://homeassistant.local:8123'
const HA_TOKEN = import.meta.env.VITE_HOMEASSISTANT_TOKEN || ''

export type { HassEntities }

export function useHomeAssistant() {
  const [entities, setEntities] = useState<HassEntities>({})
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const connectionRef = useRef<Connection | null>(null)

  useEffect(() => {
    if (!HA_TOKEN) {
      setError('No Home Assistant token configured')
      return
    }

    let unsub: (() => void) | undefined

    async function connect() {
      try {
        const auth = createLongLivedTokenAuth(HA_URL, HA_TOKEN)
        const connection = await createConnection({ auth })
        connectionRef.current = connection

        connection.addEventListener('ready', () => setIsConnected(true))
        connection.addEventListener('disconnected', () => setIsConnected(false))
        connection.addEventListener('reconnect-error', () => setIsConnected(false))

        setIsConnected(true)
        setError(null)

        unsub = subscribeEntities(connection, (ents) => {
          setEntities(ents)
        })
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to connect to Home Assistant')
        setIsConnected(false)
      }
    }

    connect()

    return () => {
      unsub?.()
      if (connectionRef.current) {
        connectionRef.current.close()
        connectionRef.current = null
      }
    }
  }, [])

  return { entities, isConnected, error }
}
