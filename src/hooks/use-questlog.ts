import { useQuery } from '@tanstack/react-query'

const QUESTLOG_URL = import.meta.env.VITE_QUESTLOG_URL || 'http://saya:7176/api'

interface CheckpointStat {
  order: number
  name: string
  trainer: string
  entered: number
  survived: number
  survival_rate: number
}

interface IronMONStats {
  challenge: string
  total_runs: number
  victories: number
  victory_rate: number
  runs_with_results: number
  checkpoints: CheckpointStat[]
}

interface Run {
  seed_number: number
  challenge: string
  highest_checkpoint: string | null
  highest_checkpoint_order: number | null
  is_victory: boolean
  started_at: string
}

interface RunList {
  runs: Run[]
  total: number
}

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
