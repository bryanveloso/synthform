import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  connectEnergy,
  fetchCurrentEnergy,
  fetchEnergyToday,
  fetchBatteries,
  fetchMicroinverters,
} from '@/api/synthhome'
import type {
  EnergySnapshot,
  EnergyEvent,
  EnergyCurrent,
  EnergyToday,
  BatteryDetail,
  MicroinverterDetail,
} from '@/api/synthhome'

export type {
  EnergySnapshot,
  EnergyEvent,
  EnergyCurrent,
  EnergyToday,
  BatteryDetail,
  MicroinverterDetail,
}

export function useEnphase() {
  const [snapshot, setSnapshot] = useState<EnergySnapshot | null>(null)
  const [lastEvent, setLastEvent] = useState<EnergyEvent | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const disconnect = connectEnergy({
      onSnapshot: setSnapshot,
      onEvent: setLastEvent,
      onConnected: () => { setIsConnected(true); setError(null) },
      onDisconnected: () => setIsConnected(false),
      onError: (err) => { setError(err); setIsConnected(false) },
    })

    return disconnect
  }, [])

  return { snapshot, lastEvent, isConnected, error }
}

export function useEnphaseCurrent() {
  return useQuery<EnergyCurrent>({
    queryKey: ['synthhome', 'energy', 'current'],
    queryFn: fetchCurrentEnergy,
    staleTime: 10_000,
    refetchInterval: 10_000,
  })
}

export function useEnphaseToday() {
  return useQuery<EnergyToday>({
    queryKey: ['synthhome', 'energy', 'today'],
    queryFn: fetchEnergyToday,
    staleTime: 60_000,
    refetchInterval: 60_000,
  })
}

export function useEnphaseBatteries() {
  return useQuery<BatteryDetail[]>({
    queryKey: ['synthhome', 'energy', 'batteries'],
    queryFn: fetchBatteries,
    staleTime: 30_000,
    refetchInterval: 30_000,
  })
}

export function useEnphaseMicroinverters() {
  return useQuery<MicroinverterDetail[]>({
    queryKey: ['synthhome', 'energy', 'inverters'],
    queryFn: fetchMicroinverters,
    staleTime: 5 * 60_000,
    refetchInterval: 5 * 60_000,
  })
}
