import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { connectTempest, fetchForecast } from '@/api/tempest'
import type {
  TempestObservation,
  TempestRapidWind,
  TempestLightningStrike,
  TempestForecast,
} from '@/api/tempest'

export type { TempestObservation, TempestRapidWind, TempestLightningStrike, TempestForecast }

export function useTempest() {
  const [observation, setObservation] = useState<TempestObservation | null>(null)
  const [rapidWind, setRapidWind] = useState<TempestRapidWind | null>(null)
  const [lastStrike, setLastStrike] = useState<TempestLightningStrike | null>(null)
  const [isRaining, setIsRaining] = useState(false)
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const disconnect = connectTempest({
      onObservation: setObservation,
      onRapidWind: setRapidWind,
      onLightningStrike: setLastStrike,
      onRainStart: () => setIsRaining(true),
      onConnected: () => { setIsConnected(true); setError(null) },
      onDisconnected: () => setIsConnected(false),
      onError: (err) => { setError(err); setIsConnected(false) },
    })

    return disconnect
  }, [])

  return { observation, rapidWind, lastStrike, isRaining, isConnected, error }
}

export function useTempestForecast() {
  return useQuery<TempestForecast>({
    queryKey: ['tempest', 'forecast'],
    queryFn: fetchForecast,
    staleTime: 15 * 60_000,
    refetchInterval: 15 * 60_000,
  })
}
