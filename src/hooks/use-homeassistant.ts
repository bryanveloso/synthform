import { useQuery } from '@tanstack/react-query'

const HA_URL = import.meta.env.VITE_HOMEASSISTANT_URL || 'http://homeassistant.local:8123'
const HA_TOKEN = import.meta.env.VITE_HOMEASSISTANT_TOKEN || ''

export interface HAState {
  entity_id: string
  state: string
  attributes: Record<string, unknown>
  last_changed: string
  last_updated: string
}

async function fetchHA<T>(path: string): Promise<T> {
  const res = await fetch(`${HA_URL}/api${path}`, {
    headers: {
      Authorization: `Bearer ${HA_TOKEN}`,
      'Content-Type': 'application/json',
    },
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export function useHAStates(refetchInterval = 5_000) {
  return useQuery<HAState[]>({
    queryKey: ['homeassistant', 'states'],
    queryFn: () => fetchHA('/states'),
    refetchInterval,
    enabled: !!HA_TOKEN,
  })
}

export function useHAEntity(entityId: string, refetchInterval = 5_000) {
  return useQuery<HAState>({
    queryKey: ['homeassistant', 'entity', entityId],
    queryFn: () => fetchHA(`/states/${entityId}`),
    refetchInterval,
    enabled: !!HA_TOKEN && !!entityId,
  })
}
