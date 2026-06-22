import { useQuery } from '@tanstack/react-query'

import type { components } from '@/api/generated/questlog'

const QUESTLOG_URL = import.meta.env.VITE_QUESTLOG_URL || 'http://saya:7176/api'

// Types generated from questlog's OpenAPI spec (see package.json `generate:api`).
type IronMONStats = components['schemas']['IronMONStatsSchema']
type RunList = components['schemas']['RunListSchema']

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${QUESTLOG_URL}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export function useIronMONStats(challenge?: string) {
  const params = challenge ? `?challenge=${challenge}` : ''
  return useQuery<IronMONStats>({
    queryKey: ['ironmon', 'stats', challenge],
    queryFn: () => fetchJSON(`/ironmon/stats${params}`),
    staleTime: 30_000,
  })
}

export function useIronMONRuns(challenge?: string, limit = 50) {
  const params = new URLSearchParams()
  if (challenge) params.set('challenge', challenge)
  if (limit !== 50) params.set('limit', String(limit))
  const qs = params.toString() ? `?${params.toString()}` : ''

  return useQuery<RunList>({
    queryKey: ['ironmon', 'runs', challenge, limit],
    queryFn: () => fetchJSON(`/ironmon/runs${qs}`),
    staleTime: 30_000,
  })
}

// ACNH types — generated from questlog's OpenAPI spec.
type ACNHVillager = components['schemas']['VillagerSchema']
type ACNHEncounter = components['schemas']['EncounterSchema']
type ACNHHunt = components['schemas']['HuntSchema']
type ACNHHuntResponse = components['schemas']['HuntResponseSchema']
type ACNHStats = components['schemas']['ACNHStatsSchema']

export type { ACNHVillager, ACNHEncounter, ACNHHunt, ACNHStats }

export function useACNHHunt() {
  return useQuery<ACNHHuntResponse>({
    queryKey: ['acnh', 'hunt', 'latest'],
    queryFn: () => fetchJSON('/acnh/hunts/latest'),
    refetchInterval: 5_000,
  })
}

export function useACNHStats() {
  return useQuery<ACNHStats>({
    queryKey: ['acnh', 'stats'],
    queryFn: () => fetchJSON('/acnh/stats'),
    staleTime: 30_000,
  })
}
