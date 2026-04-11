import {
  createLongLivedTokenAuth,
  createConnection,
  subscribeEntities,
} from 'home-assistant-js-websocket'
import type { Connection, HassEntities } from 'home-assistant-js-websocket'

const HA_URL = import.meta.env.VITE_HOMEASSISTANT_URL || 'http://homeassistant.local:8123'
const HA_TOKEN = import.meta.env.VITE_HOMEASSISTANT_TOKEN || ''

export type { HassEntities }

export interface HAConnectionOptions {
  onEntities: (entities: HassEntities) => void
  onConnected: () => void
  onDisconnected: () => void
  onError: (error: string) => void
}

export async function connectHomeAssistant(options: HAConnectionOptions): Promise<() => void> {
  if (!HA_TOKEN) {
    options.onError('No Home Assistant token configured')
    return () => {}
  }

  let connection: Connection | null = null
  let unsubEntities: (() => void) | undefined

  try {
    const auth = createLongLivedTokenAuth(HA_URL, HA_TOKEN)
    connection = await createConnection({ auth })

    connection.addEventListener('ready', () => options.onConnected())
    connection.addEventListener('disconnected', () => options.onDisconnected())
    connection.addEventListener('reconnect-error', () => options.onDisconnected())

    options.onConnected()

    unsubEntities = subscribeEntities(connection, (ents) => {
      options.onEntities(ents)
    })
  } catch (err) {
    options.onError(err instanceof Error ? err.message : 'Failed to connect to Home Assistant')
  }

  return () => {
    unsubEntities?.()
    connection?.close()
  }
}
