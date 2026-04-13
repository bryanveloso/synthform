import { useQuery } from '@tanstack/react-query'
import { fetchSteamPlayer, fetchSteamRecentGames } from '@/api/synthhome'
import type { SteamPlayer, SteamRecentGame } from '@/api/synthhome'

export type { SteamPlayer, SteamRecentGame }

export function useSteamPlayer() {
  return useQuery<SteamPlayer>({
    queryKey: ['steam', 'player'],
    queryFn: fetchSteamPlayer,
    staleTime: 60_000,
    refetchInterval: 60_000,
  })
}

export function useSteamRecentGames(count = 5) {
  return useQuery<SteamRecentGame[]>({
    queryKey: ['steam', 'recent', count],
    queryFn: () => fetchSteamRecentGames(count),
    staleTime: 5 * 60_000,
    refetchInterval: 5 * 60_000,
  })
}
