import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  connectWeather,
  fetchForecast,
  fetchCurrentWeather,
  fetchWindHistory,
} from '@/api/synthhome'
import type {
  WeatherObservation,
  WeatherRapidWind,
  WeatherLightningStrike,
  SynthhomeForecast,
  SynthhomeCurrentWeather,
  SynthhomeWindReading,
} from '@/api/synthhome'

export type {
  WeatherObservation,
  WeatherRapidWind,
  WeatherLightningStrike,
  SynthhomeForecast,
  SynthhomeCurrentWeather,
  SynthhomeWindReading,
}

export function useTempest() {
  const [observation, setObservation] = useState<WeatherObservation | null>(null)
  const [rapidWind, setRapidWind] = useState<WeatherRapidWind | null>(null)
  const [lastStrike, setLastStrike] = useState<WeatherLightningStrike | null>(null)
  const [isRaining, setIsRaining] = useState(false)
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const disconnect = connectWeather({
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
  return useQuery<SynthhomeForecast | null>({
    queryKey: ['synthhome', 'forecast'],
    queryFn: fetchForecast,
    staleTime: 15 * 60_000,
    refetchInterval: 15 * 60_000,
  })
}

export function useTempestCurrent() {
  return useQuery<SynthhomeCurrentWeather>({
    queryKey: ['synthhome', 'weather', 'current'],
    queryFn: fetchCurrentWeather,
    staleTime: 30_000,
    refetchInterval: 60_000,
  })
}

export function useTempestWindHistory(minutes = 30) {
  return useQuery<SynthhomeWindReading[]>({
    queryKey: ['synthhome', 'wind', minutes],
    queryFn: () => fetchWindHistory(minutes),
    staleTime: 30_000,
    refetchInterval: 30_000,
  })
}
